"""
KAIROS Live Data Agent — answers questions about the user's CURRENT data by
querying their connected sources on-demand (Drive, Gmail, Slack, Jira, Zoom).

Full tool set:
  Gmail  — recent, last, search, unread count, sender stats, thread stats, by-label
  Drive  — list files, count files, search by name, recent activity
  Slack  — channels, recent messages, workspace info, search messages, channel messages
  Jira   — list issues, my issues, project list, sprint status, issue stats,
            search issues, get single issue
  Zoom   — list recordings
  Multi  — dashboard snapshot (all sources at once), list connected sources
"""

from __future__ import annotations

import json
import re
import asyncio
from datetime import datetime
from typing import Any, Optional

from openai import AsyncOpenAI

from config import config
from agents.base_agent import BaseAgent, AgentTool
from core.live_connectors import build_connectors_for_user
from core.graph import DecisionNode


SYSTEM_PROMPT_TEMPLATE = """You are the KAIROS Live Data Agent. You answer the user's question by looking up their REAL, CURRENT data from the company tools they have connected.

Connected sources for this user: {connected}

You have access to these tools:
{tools}

To use a tool, output exactly:

Thought: <brief reasoning>

Action: {{"name": "tool_name", "arguments": {{"key": "value"}}}}

The system returns an Observation. Repeat Thought→Action until you have enough data, then output:

Action: {{"name": "Final Answer", "arguments": {{"answer": "..."}}}}

CRITICAL RULES:
1. DISCONNECTED SOURCE: If the user asks about a source NOT in the connected sources list (e.g. asks about email but "gmail" is not connected), IMMEDIATELY output Final Answer: "Gmail is not connected yet. Connect it in KAIROS → Connectors to see your emails." Do NOT call any tool. Do NOT loop.
2. SPECIFIC ANSWERS: Use real numbers, names, dates, and [text](url) markdown links from tool output. Never invent data.
3. HOW-MANY QUESTIONS: Call the count/stats tool first, then Final Answer with the exact number.
4. TOOL ERRORS: If a tool returns {{"error": "..."}}, report that error in Final Answer — do not retry the same tool.
5. FORMAT: Bullet lists for multiple items. Bold for key metrics. Always cite the source.

Do not output anything after the Final Answer block."""


# Map question keywords to source names — for fast early-exit when source not connected
_SOURCE_KEYWORDS: dict[str, list[str]] = {
    "gmail": ["mail", "email", "inbox", "gmail", "message", "unread", "sender", "sent"],
    "drive": ["drive", "file", "doc", "document", "sheet", "folder", "gdrive"],
    "slack": ["slack", "channel", "message", "workspace", "dm", "post"],
    "jira": ["jira", "ticket", "issue", "sprint", "backlog", "epic", "bug", "task", "story"],
    "zoom": ["zoom", "recording", "meeting", "call", "video"],
}


class LiveDataAgent(BaseAgent):
    def __init__(self, memory=None):
        super().__init__(
            name="live_data_agent",
            description="Queries the user's connected Drive/Gmail/Slack/Jira/Zoom live to answer questions about their current data",
            max_iterations=12,
        )
        self.memory = memory
        self._current_user_id: Optional[str] = None
        self._connectors: dict = {}
        self._collected_sources: list[dict] = []

        api_key, base_url, self.model = config.primary_text()
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)

    # ── Tool registration ──────────────────────────────────────────────────────

    def _register_tools(self):
        # ── Meta / multi-source ──────────────────────────────────────────────
        self.register_tool(AgentTool(
            name="list_connected_sources",
            description="List which sources (drive, gmail, slack, jira, zoom) the user has connected. Call first if unsure what's available.",
            handler=self._tool_list_connected,
            parameters={"type": "object", "properties": {}},
        ))
        self.register_tool(AgentTool(
            name="dashboard_snapshot",
            description="Get a quick summary from ALL connected sources at once: unread email count, Drive file count, open Jira issues, recent Slack activity. Use for 'give me a status update', 'what's happening', 'what do I have'.",
            handler=self._tool_dashboard,
            parameters={"type": "object", "properties": {}},
        ))

        # ── Gmail ────────────────────────────────────────────────────────────
        self.register_tool(AgentTool(
            name="gmail_unread_count",
            description="Get the number of unread emails in inbox and other labels (Promotions, Social, Updates). Use for 'how many unread emails', 'how many emails do I have'.",
            handler=self._tool_gmail_unread,
            parameters={"type": "object", "properties": {}},
        ))
        self.register_tool(AgentTool(
            name="gmail_thread_stats",
            description="Get total email/thread count + top 5 senders from the last 30 days. Use for 'who emails me the most', 'how many total emails'.",
            handler=self._tool_gmail_stats,
            parameters={"type": "object", "properties": {}},
        ))
        self.register_tool(AgentTool(
            name="gmail_recent",
            description="List the user's most recent emails from inbox. Optional 'limit' (default 10, max 30).",
            handler=self._tool_gmail_recent,
            parameters={"type": "object", "properties": {"limit": {"type": "integer"}}},
        ))
        self.register_tool(AgentTool(
            name="gmail_last",
            description="Get the single most recent email. Optional 'from_sender' to filter by sender name or email.",
            handler=self._tool_gmail_last,
            parameters={"type": "object", "properties": {"from_sender": {"type": "string"}}},
        ))
        self.register_tool(AgentTool(
            name="gmail_search",
            description="Search emails using a Gmail query string. Examples: 'from:priya@company.com', 'subject:invoice', 'is:unread', 'has:attachment', 'contract after:2026/01/01'. Args: 'query' (required), 'limit' (default 10).",
            handler=self._tool_gmail_search,
            parameters={"type": "object", "properties": {
                "query": {"type": "string"}, "limit": {"type": "integer"}},
                "required": ["query"]},
        ))
        self.register_tool(AgentTool(
            name="gmail_by_label",
            description="Get emails from a specific Gmail label. label options: INBOX, STARRED, IMPORTANT, SENT, SPAM, CATEGORY_PROMOTIONS, CATEGORY_SOCIAL, CATEGORY_UPDATES. Args: 'label' (required), 'limit' (default 10).",
            handler=self._tool_gmail_by_label,
            parameters={"type": "object", "properties": {
                "label": {"type": "string"}, "limit": {"type": "integer"}},
                "required": ["label"]},
        ))
        self.register_tool(AgentTool(
            name="gmail_sender_stats",
            description="Get top senders by email volume over the last N days. Args: 'days_back' (default 30), 'top_n' (default 10). Use for 'who emails me most', 'top senders'.",
            handler=self._tool_gmail_sender_stats,
            parameters={"type": "object", "properties": {
                "days_back": {"type": "integer"}, "top_n": {"type": "integer"}}},
        ))

        # ── Google Drive ─────────────────────────────────────────────────────
        self.register_tool(AgentTool(
            name="drive_count_files",
            description="Count total files in Google Drive with a breakdown by file type (Docs, Sheets, PDFs, etc.).",
            handler=self._tool_drive_count,
            parameters={"type": "object", "properties": {}},
        ))
        self.register_tool(AgentTool(
            name="drive_list_files",
            description="List the user's most recently modified Drive files. Optional 'name_query' to filter by filename, 'limit' (default 15).",
            handler=self._tool_drive_list,
            parameters={"type": "object", "properties": {
                "name_query": {"type": "string"}, "limit": {"type": "integer"}}},
        ))
        self.register_tool(AgentTool(
            name="drive_search",
            description="Search Drive files by name keyword. Args: 'query' (required), 'limit' (default 10). Use for 'find files about X', 'do I have a doc called Y'.",
            handler=self._tool_drive_search,
            parameters={"type": "object", "properties": {
                "query": {"type": "string"}, "limit": {"type": "integer"}},
                "required": ["query"]},
        ))

        # ── Slack ────────────────────────────────────────────────────────────
        self.register_tool(AgentTool(
            name="slack_workspace_info",
            description="Get Slack workspace overview: name, member count, channel count, bot count. Use for 'how many people on Slack', 'Slack workspace stats'.",
            handler=self._tool_slack_workspace,
            parameters={"type": "object", "properties": {}},
        ))
        self.register_tool(AgentTool(
            name="slack_list_channels",
            description="List all Slack channels the KAIROS bot can see with their member counts.",
            handler=self._tool_slack_channels,
            parameters={"type": "object", "properties": {}},
        ))
        self.register_tool(AgentTool(
            name="slack_recent_messages",
            description="List recent messages across all Slack channels. Optional 'limit' (default 15).",
            handler=self._tool_slack_recent,
            parameters={"type": "object", "properties": {"limit": {"type": "integer"}}},
        ))
        self.register_tool(AgentTool(
            name="slack_search_messages",
            description="Search Slack messages for a keyword or phrase. Args: 'query' (required), 'limit' (default 10). Use for 'find Slack messages about X', 'who mentioned Y in Slack'.",
            handler=self._tool_slack_search,
            parameters={"type": "object", "properties": {
                "query": {"type": "string"}, "limit": {"type": "integer"}},
                "required": ["query"]},
        ))
        self.register_tool(AgentTool(
            name="slack_channel_messages",
            description="Get recent messages from a specific Slack channel. Args: 'channel_name' (required, without #), 'limit' (default 20).",
            handler=self._tool_slack_channel_msgs,
            parameters={"type": "object", "properties": {
                "channel_name": {"type": "string"}, "limit": {"type": "integer"}},
                "required": ["channel_name"]},
        ))

        # ── Jira ─────────────────────────────────────────────────────────────
        self.register_tool(AgentTool(
            name="jira_list_issues",
            description="List recently created or updated Jira issues (last 30 days). Optional 'limit' (default 15).",
            handler=self._tool_jira_list,
            parameters={"type": "object", "properties": {"limit": {"type": "integer"}}},
        ))
        self.register_tool(AgentTool(
            name="jira_my_issues",
            description="Get Jira issues assigned to the current user. Optional 'status_filter' (e.g. 'In Progress', 'To Do', 'Done'). Use for 'what are my tickets', 'what am I working on'.",
            handler=self._tool_jira_my_issues,
            parameters={"type": "object", "properties": {"status_filter": {"type": "string"}}},
        ))
        self.register_tool(AgentTool(
            name="jira_project_list",
            description="List all Jira projects in the workspace with lead and key. Use for 'what projects are in Jira', 'list all Jira projects'.",
            handler=self._tool_jira_projects,
            parameters={"type": "object", "properties": {}},
        ))
        self.register_tool(AgentTool(
            name="jira_issue_stats",
            description="Get a count of Jira issues by status across the workspace (To Do, In Progress, Done, Blocked, etc.). Use for 'how many open tickets', 'Jira overview'.",
            handler=self._tool_jira_stats,
            parameters={"type": "object", "properties": {}},
        ))
        self.register_tool(AgentTool(
            name="jira_sprint_status",
            description="Get active sprint info for Scrum boards (sprint name, dates, goal). Optional 'project_key' to narrow to a specific project.",
            handler=self._tool_jira_sprint,
            parameters={"type": "object", "properties": {"project_key": {"type": "string"}}},
        ))
        self.register_tool(AgentTool(
            name="jira_search_issues",
            description="Full-text search across Jira issue summaries and descriptions. Args: 'query' (required), 'limit' (default 15). Use for 'find Jira tickets about X'.",
            handler=self._tool_jira_search,
            parameters={"type": "object", "properties": {
                "query": {"type": "string"}, "limit": {"type": "integer"}},
                "required": ["query"]},
        ))
        self.register_tool(AgentTool(
            name="jira_get_issue",
            description="Get full details of a single Jira issue by key (e.g. 'KAI-42'). Args: 'issue_key' (required).",
            handler=self._tool_jira_issue,
            parameters={"type": "object", "properties": {"issue_key": {"type": "string"}},
                "required": ["issue_key"]},
        ))

        # ── Zoom ─────────────────────────────────────────────────────────────
        self.register_tool(AgentTool(
            name="zoom_list_recordings",
            description="List recent Zoom cloud recordings with topic, date, duration, and link. Optional 'limit' (default 10).",
            handler=self._tool_zoom_list,
            parameters={"type": "object", "properties": {"limit": {"type": "integer"}}},
        ))

        # ── Memory cache fallback ─────────────────────────────────────────────
        self.register_tool(AgentTool(
            name="search_cached_items",
            description="Search KAIROS's previously-ingested decision cache when a live source is unavailable. Args: 'query' (str), 'source' (optional: drive|email|slack|jira|zoom).",
            handler=self._tool_search_inventory,
            parameters={"type": "object", "properties": {
                "query": {"type": "string"}, "source": {"type": "string"}},
                "required": ["query"]},
        ))

    # ── Tool handlers ──────────────────────────────────────────────────────────

    def _add_source(self, title: str, date: str, source: str, url: str):
        if url and len(self._collected_sources) < 12:
            # Use deterministic ID matching memory.make_id() so frontend /api/decisions/<id> works
            node_id = (
                self.memory.make_id(title=title, source_url=url, user_id=self._current_user_id)
                if self.memory and title
                else url
            )
            self._collected_sources.append({
                "id": node_id, "title": title or source, "date": date or "",
                "source": source, "source_url": url,
            })

    def _write_sources_to_graph(self):
        """Store collected live-data sources as DecisionNodes in KAIROS memory."""
        if not self.memory or not self._collected_sources:
            return
        for src in self._collected_sources[:8]:
            try:
                node = DecisionNode(
                    id=src["id"],
                    title=src["title"],
                    summary=f"Live data fetched from {src['source']}",
                    date=src.get("date", ""),
                    source=src["source"].lower(),
                    source_url=src["source_url"],
                    topics=[src["source"]],
                    participants=[],
                    outcome=f"Retrieved from {src['source']}: {src['title']}",
                    user_id=self._current_user_id or "",
                )
                self.memory.store(node, user_id=self._current_user_id)
            except Exception as e:
                print(f"[LiveDataAgent] graph write error: {e}")

    # Meta
    async def _tool_list_connected(self) -> dict:
        connected = self._connectors.get("connected", [])
        return {
            "connected": connected,
            "not_connected": [s for s in ("drive", "gmail", "slack", "jira", "zoom") if s not in connected],
        }

    async def _tool_dashboard(self) -> dict:
        """Fire quick queries across all connected sources simultaneously."""
        connected = self._connectors.get("connected", [])
        result: dict = {"connected_sources": connected}
        tasks = []

        async def _gmail_summary():
            c = self._connectors.get("gmail")
            if not c:
                return
            try:
                unread = await c.count_unread()
                result["gmail"] = {
                    "total_unread": unread.get("total_unread", 0),
                    "inbox_threads_unread": unread.get("inbox_threads_unread", 0),
                    "total_messages": unread.get("total_messages", 0),
                }
            except Exception as e:
                result["gmail"] = {"error": str(e)}

        async def _drive_summary():
            c = self._connectors.get("drive")
            if not c:
                return
            try:
                info = await c.count_files()
                result["drive"] = {"total_files": info.get("total", 0), "by_type": info.get("by_type", {})}
            except Exception as e:
                result["drive"] = {"error": str(e)}

        async def _jira_summary():
            c = self._connectors.get("jira")
            if not c:
                return
            try:
                stats = await c.get_issue_stats()
                result["jira"] = stats
            except Exception as e:
                result["jira"] = {"error": str(e)}

        async def _slack_summary():
            c = self._connectors.get("slack")
            if not c:
                return
            try:
                info = await c.get_workspace_info()
                result["slack"] = info
            except Exception as e:
                result["slack"] = {"error": str(e)}

        if "gmail" in connected:
            tasks.append(_gmail_summary())
        if "drive" in connected:
            tasks.append(_drive_summary())
        if "jira" in connected:
            tasks.append(_jira_summary())
        if "slack" in connected:
            tasks.append(_slack_summary())

        await asyncio.gather(*tasks)
        return result

    # Gmail
    async def _tool_gmail_unread(self) -> dict:
        c = self._connectors.get("gmail")
        if not c:
            return {"error": "Gmail is not connected."}
        return await c.count_unread()

    async def _tool_gmail_stats(self) -> dict:
        c = self._connectors.get("gmail")
        if not c:
            return {"error": "Gmail is not connected."}
        return await c.get_thread_stats()

    async def _tool_gmail_recent(self, limit: int = 10) -> Any:
        c = self._connectors.get("gmail")
        if not c:
            return {"error": "Gmail is not connected."}
        emails = await c.get_recent(limit=min(limit, 30))
        return {"count": len(emails), "emails": [self._fmt_email(e) for e in emails]}

    async def _tool_gmail_last(self, from_sender: str = None) -> Any:
        c = self._connectors.get("gmail")
        if not c:
            return {"error": "Gmail is not connected."}
        email = await c.get_last(from_sender=from_sender)
        if not email:
            return {"result": "No matching email found."}
        return self._fmt_email(email)

    async def _tool_gmail_search(self, query: str, limit: int = 10) -> Any:
        c = self._connectors.get("gmail")
        if not c:
            return {"error": "Gmail is not connected."}
        emails = await c.get_recent(limit=min(limit, 30), query=query)
        return {"count": len(emails), "emails": [self._fmt_email(e) for e in emails]}

    async def _tool_gmail_by_label(self, label: str, limit: int = 10) -> Any:
        c = self._connectors.get("gmail")
        if not c:
            return {"error": "Gmail is not connected."}
        emails = await c.get_by_label(label=label, limit=min(limit, 30))
        return {"count": len(emails), "label": label, "emails": [self._fmt_email(e) for e in emails]}

    async def _tool_gmail_sender_stats(self, days_back: int = 30, top_n: int = 10) -> Any:
        c = self._connectors.get("gmail")
        if not c:
            return {"error": "Gmail is not connected."}
        return {"top_senders": await c.get_sender_stats(days_back=days_back, top_n=top_n)}

    def _fmt_email(self, e: dict) -> dict:
        self._add_source(e.get("subject", ""), e.get("date", ""), "Gmail", e.get("source_url", ""))
        return {
            "subject": e.get("subject", ""),
            "from": e.get("from_", ""),
            "date": e.get("date", ""),
            "unread": e.get("unread", False),
            "snippet": (e.get("snippet", "") or "")[:250],
            "url": e.get("source_url", ""),
        }

    # Drive
    async def _tool_drive_count(self) -> dict:
        c = self._connectors.get("drive")
        if not c:
            return {"error": "Google Drive is not connected."}
        return await c.count_files()

    async def _tool_drive_list(self, name_query: str = None, limit: int = 15) -> Any:
        c = self._connectors.get("drive")
        if not c:
            return {"error": "Google Drive is not connected."}
        files = await c.list_all_files(limit=limit, name_query=name_query)
        out = []
        for f in files:
            self._add_source(f.get("name", ""), (f.get("modifiedTime", "") or "")[:10], "Google Drive", f.get("webViewLink", ""))
            out.append({
                "name": f.get("name", ""),
                "type": f.get("friendlyType", ""),
                "modified": (f.get("modifiedTime", "") or "")[:10],
                "url": f.get("webViewLink", ""),
            })
        return {"count": len(out), "files": out}

    async def _tool_drive_search(self, query: str, limit: int = 10) -> Any:
        c = self._connectors.get("drive")
        if not c:
            return {"error": "Google Drive is not connected."}
        files = await c.list_all_files(limit=limit, name_query=query)
        out = []
        for f in files:
            self._add_source(f.get("name", ""), (f.get("modifiedTime", "") or "")[:10], "Google Drive", f.get("webViewLink", ""))
            out.append({
                "name": f.get("name", ""),
                "type": f.get("friendlyType", ""),
                "modified": (f.get("modifiedTime", "") or "")[:10],
                "url": f.get("webViewLink", ""),
            })
        return {"count": len(out), "query": query, "files": out}

    # Slack
    async def _tool_slack_workspace(self) -> Any:
        c = self._connectors.get("slack")
        if not c:
            return {"error": "Slack is not connected."}
        return await c.get_workspace_info()

    async def _tool_slack_channels(self) -> Any:
        c = self._connectors.get("slack")
        if not c:
            return {"error": "Slack is not connected."}
        channels = await c.get_channels()
        out = []
        for ch in channels:
            out.append({
                "name": ch.get("name", ""),
                "members": ch.get("num_members", 0),
                "topic": (ch.get("topic") or {}).get("value", "") or "",
                "purpose": (ch.get("purpose") or {}).get("value", "") or "",
            })
        return {"count": len(out), "channels": out}

    async def _tool_slack_recent(self, limit: int = 15) -> Any:
        c = self._connectors.get("slack")
        if not c:
            return {"error": "Slack is not connected."}
        msgs = await c.get_recent_messages(limit=limit)
        out = []
        for m in msgs:
            try:
                date = datetime.utcfromtimestamp(float(m.get("ts", "0"))).strftime("%Y-%m-%d %H:%M")
            except (ValueError, TypeError):
                date = ""
            self._add_source(f"#{m.get('channel_name','')} — {m.get('user','')}", date[:10], "Slack", m.get("permalink", ""))
            out.append({
                "channel": f"#{m.get('channel_name', '')}",
                "user": m.get("user", ""),
                "text": (m.get("text", "") or "")[:300],
                "date": date,
                "url": m.get("permalink", ""),
            })
        return {"count": len(out), "messages": out}

    async def _tool_slack_search(self, query: str, limit: int = 10) -> Any:
        c = self._connectors.get("slack")
        if not c:
            return {"error": "Slack is not connected."}
        # Use recent messages filtered by keyword since Slack search needs a user token
        msgs = await c.get_recent_messages(limit=200)
        filtered = [m for m in msgs if query.lower() in (m.get("text", "") or "").lower()][:limit]
        out = []
        for m in filtered:
            try:
                date = datetime.utcfromtimestamp(float(m.get("ts", "0"))).strftime("%Y-%m-%d")
            except (ValueError, TypeError):
                date = ""
            out.append({
                "channel": f"#{m.get('channel_name', '')}",
                "user": m.get("user", ""),
                "text": (m.get("text", "") or "")[:300],
                "date": date,
                "url": m.get("permalink", ""),
            })
        return {"count": len(out), "query": query, "messages": out}

    async def _tool_slack_channel_msgs(self, channel_name: str, limit: int = 20) -> Any:
        c = self._connectors.get("slack")
        if not c:
            return {"error": "Slack is not connected."}
        # Find the channel ID by name
        channels = await c.get_channels()
        channel_id = None
        name_clean = channel_name.lstrip("#")
        for ch in channels:
            if ch.get("name", "").lower() == name_clean.lower():
                channel_id = ch.get("id")
                break
        if not channel_id:
            return {"error": f"Channel #{name_clean} not found. Try slack_list_channels to see available channels."}
        msgs = await c.get_channel_messages(channel_id=channel_id, limit=limit)
        out = []
        for m in msgs:
            try:
                date = datetime.utcfromtimestamp(float(m.get("ts", "0"))).strftime("%Y-%m-%d %H:%M")
            except (ValueError, TypeError):
                date = ""
            out.append({
                "user": m.get("user", ""),
                "text": (m.get("text", "") or "")[:300],
                "date": date,
            })
        return {"channel": f"#{name_clean}", "count": len(out), "messages": out}

    # Jira
    async def _tool_jira_list(self, limit: int = 15) -> Any:
        c = self._connectors.get("jira")
        if not c:
            return {"error": "Jira is not connected."}
        issues = await c.get_recent_issues(days_back=30)
        return self._fmt_issues(issues[:limit])

    async def _tool_jira_my_issues(self, status_filter: str = None) -> Any:
        c = self._connectors.get("jira")
        if not c:
            return {"error": "Jira is not connected."}
        issues = await c.get_my_issues(status_filter=status_filter)
        return self._fmt_issues(issues)

    async def _tool_jira_projects(self) -> Any:
        c = self._connectors.get("jira")
        if not c:
            return {"error": "Jira is not connected."}
        projects = await c.get_projects()
        for p in projects:
            self._add_source(p.get("name", ""), "", "Jira", p.get("url", ""))
        return {"count": len(projects), "projects": projects}

    async def _tool_jira_stats(self) -> Any:
        c = self._connectors.get("jira")
        if not c:
            return {"error": "Jira is not connected."}
        return await c.get_issue_stats()

    async def _tool_jira_sprint(self, project_key: str = None) -> Any:
        c = self._connectors.get("jira")
        if not c:
            return {"error": "Jira is not connected."}
        return await c.get_sprint_status(project_key=project_key)

    async def _tool_jira_search(self, query: str, limit: int = 15) -> Any:
        c = self._connectors.get("jira")
        if not c:
            return {"error": "Jira is not connected."}
        issues = await c.search_issues(query=query, limit=limit)
        return self._fmt_issues(issues)

    async def _tool_jira_issue(self, issue_key: str) -> Any:
        c = self._connectors.get("jira")
        if not c:
            return {"error": "Jira is not connected."}
        issue = await c.get_issue(issue_key)
        if not issue:
            return {"error": f"Issue {issue_key} not found."}
        self._add_source(f"{issue['key']}: {issue['summary']}", issue.get("updated", ""), "Jira", issue.get("source_url", ""))
        return issue

    def _fmt_issues(self, issues: list[dict]) -> dict:
        out = []
        for i in issues:
            self._add_source(f"{i.get('key','')}: {i.get('summary','')}", i.get("updated", ""), "Jira", i.get("source_url", ""))
            out.append({
                "key": i.get("key", ""),
                "summary": i.get("summary", ""),
                "status": i.get("status", ""),
                "priority": i.get("priority", ""),
                "type": i.get("type", ""),
                "assignee": i.get("assignee", ""),
                "updated": i.get("updated", ""),
                "url": i.get("source_url", ""),
            })
        return {"count": len(out), "issues": out}

    # Zoom
    async def _tool_zoom_list(self, limit: int = 10) -> Any:
        c = self._connectors.get("zoom")
        if not c:
            return {"error": "Zoom is not connected."}
        recs = await c.get_recordings(days_back=30)
        out = []
        for r in recs[:limit]:
            self._add_source(r.get("topic", "Zoom meeting"), (r.get("start_time", "") or "")[:10], "Zoom", r.get("share_url", ""))
            out.append({
                "topic": r.get("topic", ""),
                "start_time": (r.get("start_time", "") or "")[:16].replace("T", " "),
                "duration_min": r.get("duration", 0),
                "url": r.get("share_url", ""),
            })
        return {"count": len(out), "recordings": out}

    # Cache fallback
    async def _tool_search_inventory(self, query: str = None, source: str = None) -> Any:
        if not self.memory:
            return {"error": "No cached inventory available."}
        rows = self.memory.search_inventory(self._current_user_id, query=query, source=source, limit=20)
        for r in rows:
            self._add_source(r.get("title", ""), r.get("item_date", ""), r.get("source", "cache"), r.get("url", ""))
        return {"count": len(rows), "items": rows}

    # ── ReAct loop ─────────────────────────────────────────────────────────────

    async def execute(self, input_data: Any, **kwargs) -> dict:
        question = input_data if isinstance(input_data, str) else str(input_data)
        self._current_user_id = kwargs.get("user_id")
        self._collected_sources = []

        self._connectors = await asyncio.to_thread(build_connectors_for_user, self._current_user_id or "")
        connected = self._connectors.get("connected", [])
        self.think(f"Connected sources: {connected or 'none'}")

        if not connected:
            answer = (
                "No data sources are connected yet. Go to **KAIROS → Connectors** and connect "
                "Google Drive, Gmail, Slack, Jira, or Zoom to start querying your live data."
            )
            await self._maybe_stream(answer, kwargs.get("stream_callback"))
            return {"answer": answer, "sources": [], "query": question}

        # Early-exit: detect if the user needs a source that isn't connected
        q_lower = question.lower()
        for source_name, keywords in _SOURCE_KEYWORDS.items():
            if source_name not in connected and any(kw in q_lower for kw in keywords):
                source_display = {"gmail": "Gmail", "drive": "Google Drive", "slack": "Slack",
                                  "jira": "Jira", "zoom": "Zoom"}.get(source_name, source_name.title())
                answer = (
                    f"**{source_display} is not connected.** Go to **KAIROS → Connectors** and "
                    f"click Connect on {source_display} to enable this. Once connected, ask me again."
                )
                await self._maybe_stream(answer, kwargs.get("stream_callback"))
                return {"answer": answer, "sources": [], "query": question}

        system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
            connected=", ".join(connected) or "none",
            tools=self.get_tools_description(),
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"User question: {question}"},
        ]

        final_answer = ""
        for iteration in range(self.max_iterations):
            try:
                response = await self._chat_completion_with_fallback(
                    client=self._client, model=self.model, messages=messages,
                    temperature=0.1, max_tokens=1200,
                )
                raw = response.choices[0].message.content.strip()

                thought_match = re.search(r"Thought:\s*(.*?)(?=\nAction:|$)", raw, re.DOTALL | re.IGNORECASE)
                action_match = re.search(r"Action:\s*(\{.*\})", raw, re.DOTALL | re.IGNORECASE)

                if thought_match:
                    self.think(thought_match.group(1).strip())
                    messages.append({"role": "assistant", "content": f"Thought: {thought_match.group(1).strip()}"})

                if not action_match:
                    json_match = re.search(r"(\{.*\})", raw, re.DOTALL)
                    if not json_match:
                        raise ValueError(f"No Action block in: {raw[:200]}")
                    action_json_str = json_match.group(1).strip()
                else:
                    action_json_str = action_match.group(1).strip()

                action_data = json.loads(action_json_str)
                tool_name = action_data.get("name")
                tool_args = action_data.get("arguments", {}) or {}

                if tool_name == "Final Answer":
                    final_answer = tool_args.get("answer", "")
                    self.reflect("Live lookup complete.")
                    break

                self.think(f"Calling {tool_name}({json.dumps(tool_args)})")
                observation = await self.use_tool(tool_name, **tool_args)
                obs_str = json.dumps(observation, indent=2)[:3000]
                self.observe(f"{tool_name} → {str(observation)[:200]}")
                messages.append({"role": "user", "content": f"Observation from {tool_name}:\n{obs_str}"})

            except Exception as e:
                self.observe(f"ReAct step error: {e}")
                messages.append({"role": "user", "content": f"Error on iteration {iteration}: {e}. Adjust your format or pick a different tool."})

        if not final_answer:
            if self._collected_sources:
                items = "\n".join(
                    f"- [{s['title']}]({s['source_url']}) — {s['source']}"
                    for s in self._collected_sources[:6] if s.get("source_url")
                )
                final_answer = f"Here's what I found from your connected sources:\n\n{items}"
            else:
                not_connected = [s for s in ("gmail", "drive", "slack", "jira", "zoom") if s not in connected]
                tip = f" (Not yet connected: {', '.join(not_connected)})" if not_connected else ""
                final_answer = (
                    f"I couldn't fetch data for this query from your connected sources "
                    f"({', '.join(connected)}){tip}. Try reconnecting them in KAIROS → Connectors."
                )

        # Write fetched live items into the decision graph so they appear as nodes
        await asyncio.to_thread(self._write_sources_to_graph)

        await self._maybe_stream(final_answer, kwargs.get("stream_callback"))
        return {
            "answer": final_answer,
            "sources": self._collected_sources[:8],
            "query": question,
        }

    async def _maybe_stream(self, text: str, stream_callback):
        if not stream_callback:
            return
        for token in re.split(r"(\s+)", text):
            if token:
                await stream_callback({"type": "token", "content": token})
                await asyncio.sleep(0.005)

    async def evaluate_confidence(self, _input_data: Any, output: Any) -> float:
        if isinstance(output, dict):
            ans = output.get("answer", "")
            if "unable to retrieve" in ans or "don't have any data sources" in ans:
                return 0.25
            if "couldn't generate a complete summary" in ans:
                return 0.4
            if output.get("sources"):
                return 0.92
            return 0.75
        return 0.5
