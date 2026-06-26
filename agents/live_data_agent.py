"""
KAIROS Live Data Agent — answers questions about the user's CURRENT data by
querying their connected sources on-demand (Drive, Gmail, Slack, Jira, Zoom),
instead of only reading pre-extracted decisions from memory.

Handles things like:
  - "What's in my Drive?" / "How many files do I have?"
  - "Show my last email" / "Any recent emails from Priya?"
  - "What are my recent Slack messages?" / "List my Jira tickets"

Mirrors the ResearchAgent's text-based ReAct loop (Thought → Action(JSON) →
Observation), but its tools build per-user connectors from stored OAuth tokens
via core.live_connectors. Data fetches hit the source APIs directly; only the
final answer uses the LLM, so this is cheap on the LLM token budget.

Returns the same {answer, sources, query} shape as the synthesis agent so the
existing UI renders it with no frontend changes.
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


SYSTEM_PROMPT_TEMPLATE = """You are the KAIROS Live Data Agent. You answer the user's question by looking up their REAL, CURRENT data from the company tools they have connected.

Connected sources for this user: {connected}

You have access to these tools:
{tools}

To use a tool, output a Thought then an Action block, exactly in this format:

Thought: brief reasoning about which tool answers the question.

Action: {{"name": "tool_name", "arguments": {{"arg1": "val1"}}}}

The system runs the tool and returns an Observation. Repeat as needed (usually 1-2 tools is enough).
When you have what you need, output your final answer as:

Action: {{"name": "Final Answer", "arguments": {{"answer": "..."}}}}

Rules for the final answer:
- Answer naturally and specifically using ONLY the data the tools returned. Give real counts, names, dates. Format lists as markdown with links like [name](url) when a url is present.
- If a tool reports a source is not connected, tell the user that source isn't connected yet and they can connect it in KAIROS — don't invent data.
- If the question isn't about the user's company/connected data at all (general knowledge, small talk), answer briefly and note that it's general info, not from their connected sources.
- Never tell the user to "contact an administrator" or invent files/emails/links.

Do not output anything after the Action block."""


class LiveDataAgent(BaseAgent):
    def __init__(self, memory=None):
        super().__init__(
            name="live_data_agent",
            description="Queries the user's connected Drive/Gmail/Slack/Jira/Zoom live to answer questions about their current data",
            max_iterations=6,
        )
        self.memory = memory
        self._current_user_id: Optional[str] = None
        self._connectors: dict = {}
        self._collected_sources: list[dict] = []

        api_key = config.GROQ_API_KEY or config.FIREWORKS_API_KEY
        base_url = config.GROQ_BASE_URL if config.GROQ_API_KEY else config.FIREWORKS_BASE_URL
        self.model = config.GROQ_MODEL if config.GROQ_API_KEY else config.FIREWORKS_MODEL
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)

    # ── Tools ──────────────────────────────────────────────────────────────────

    def _register_tools(self):
        self.register_tool(AgentTool(
            name="list_connected_sources",
            description="List which sources (drive, gmail, slack, jira, zoom) the user has connected. Use first if unsure.",
            handler=self._tool_list_connected,
            parameters={"type": "object", "properties": {}},
        ))
        self.register_tool(AgentTool(
            name="drive_count_files",
            description="Count how many files are in the user's Google Drive (with a breakdown by type).",
            handler=self._tool_drive_count,
            parameters={"type": "object", "properties": {}},
        ))
        self.register_tool(AgentTool(
            name="drive_list_files",
            description="List the user's most recent Drive files (any type). Optional 'name_query' to filter by name, 'limit' (default 15).",
            handler=self._tool_drive_list,
            parameters={"type": "object", "properties": {
                "name_query": {"type": "string"}, "limit": {"type": "integer"}}},
        ))
        self.register_tool(AgentTool(
            name="gmail_recent",
            description="List the user's most recent emails. Optional 'limit' (default 10).",
            handler=self._tool_gmail_recent,
            parameters={"type": "object", "properties": {"limit": {"type": "integer"}}},
        ))
        self.register_tool(AgentTool(
            name="gmail_last",
            description="Get the single most recent email. Optional 'from_sender' to filter to a sender.",
            handler=self._tool_gmail_last,
            parameters={"type": "object", "properties": {"from_sender": {"type": "string"}}},
        ))
        self.register_tool(AgentTool(
            name="gmail_search",
            description="Search the user's email with a Gmail query (e.g. 'from:priya', 'invoice'). Args: 'query' (str), 'limit' (int).",
            handler=self._tool_gmail_search,
            parameters={"type": "object", "properties": {
                "query": {"type": "string"}, "limit": {"type": "integer"}}, "required": ["query"]},
        ))
        self.register_tool(AgentTool(
            name="slack_list_channels",
            description="List the Slack channels the user's KAIROS bot can see.",
            handler=self._tool_slack_channels,
            parameters={"type": "object", "properties": {}},
        ))
        self.register_tool(AgentTool(
            name="slack_recent_messages",
            description="List recent Slack messages across the user's channels. Optional 'limit' (default 15).",
            handler=self._tool_slack_recent,
            parameters={"type": "object", "properties": {"limit": {"type": "integer"}}},
        ))
        self.register_tool(AgentTool(
            name="jira_list_issues",
            description="List the user's recent Jira issues/tickets. Optional 'limit' (default 15).",
            handler=self._tool_jira_list,
            parameters={"type": "object", "properties": {"limit": {"type": "integer"}}},
        ))
        self.register_tool(AgentTool(
            name="zoom_list_recordings",
            description="List the user's recent Zoom cloud recordings. Optional 'limit' (default 15).",
            handler=self._tool_zoom_list,
            parameters={"type": "object", "properties": {"limit": {"type": "integer"}}},
        ))
        self.register_tool(AgentTool(
            name="search_my_items",
            description="Search KAIROS's cached snapshot of previously-ingested items (files/emails/messages) when a live source is slow or disconnected. Args: 'query' (str), 'source' (str: drive|email|slack|jira|zoom).",
            handler=self._tool_search_inventory,
            parameters={"type": "object", "properties": {
                "query": {"type": "string"}, "source": {"type": "string"}}},
        ))

    # ── Tool handlers ──────────────────────────────────────────────────────────

    def _add_source(self, title: str, date: str, source: str, url: str):
        if url and len(self._collected_sources) < 12:
            self._collected_sources.append({
                "id": url, "title": title or source, "date": date or "",
                "source": source, "source_url": url,
            })

    async def _tool_list_connected(self) -> dict:
        connected = self._connectors.get("connected", [])
        return {"connected": connected, "not_connected": [
            s for s in ("drive", "gmail", "slack", "jira", "zoom") if s not in connected
        ]}

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

    async def _tool_gmail_recent(self, limit: int = 10) -> Any:
        c = self._connectors.get("gmail")
        if not c:
            return {"error": "Gmail is not connected."}
        emails = await c.get_recent(limit=limit)
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
        emails = await c.get_recent(limit=limit, query=query)
        return {"count": len(emails), "emails": [self._fmt_email(e) for e in emails]}

    def _fmt_email(self, e: dict) -> dict:
        self._add_source(e.get("subject", ""), e.get("date", ""), "Gmail", e.get("source_url", ""))
        return {
            "subject": e.get("subject", ""),
            "from": e.get("from_", ""),
            "date": e.get("date", ""),
            "snippet": (e.get("snippet", "") or "")[:200],
            "url": e.get("source_url", ""),
        }

    async def _tool_slack_channels(self) -> Any:
        c = self._connectors.get("slack")
        if not c:
            return {"error": "Slack is not connected."}
        channels = await c.get_channels()
        return {"count": len(channels), "channels": [ch.get("name", "") for ch in channels]}

    async def _tool_slack_recent(self, limit: int = 15) -> Any:
        c = self._connectors.get("slack")
        if not c:
            return {"error": "Slack is not connected."}
        msgs = await c.get_recent_messages(limit=limit)
        out = []
        for m in msgs:
            try:
                date = datetime.utcfromtimestamp(float(m.get("ts", "0"))).strftime("%Y-%m-%d")
            except (ValueError, TypeError):
                date = ""
            self._add_source(f"#{m.get('channel_name','')} — {m.get('user','')}", date, "Slack", m.get("permalink", ""))
            out.append({
                "channel": m.get("channel_name", ""),
                "user": m.get("user", ""),
                "text": (m.get("text", "") or "")[:200],
                "date": date,
                "url": m.get("permalink", ""),
            })
        return {"count": len(out), "messages": out}

    async def _tool_jira_list(self, limit: int = 15) -> Any:
        c = self._connectors.get("jira")
        if not c:
            return {"error": "Jira is not connected."}
        issues = await c.get_recent_issues(days_back=30)
        out = []
        for i in issues[:limit]:
            self._add_source(f"{i.get('key','')}: {i.get('summary','')}", i.get("updated", ""), "Jira", i.get("source_url", ""))
            out.append({
                "key": i.get("key", ""),
                "summary": i.get("summary", ""),
                "status": i.get("status", ""),
                "assignee": i.get("assignee", ""),
                "updated": i.get("updated", ""),
                "url": i.get("source_url", ""),
            })
        return {"count": len(out), "issues": out}

    async def _tool_zoom_list(self, limit: int = 15) -> Any:
        c = self._connectors.get("zoom")
        if not c:
            return {"error": "Zoom is not connected."}
        recs = await c.get_recordings(days_back=30)
        out = []
        for r in recs[:limit]:
            self._add_source(r.get("topic", "Zoom meeting"), (r.get("start_time", "") or "")[:10], "Zoom", r.get("share_url", ""))
            out.append({
                "topic": r.get("topic", ""),
                "start_time": (r.get("start_time", "") or "")[:10],
                "duration_min": r.get("duration", 0),
                "url": r.get("share_url", ""),
            })
        return {"count": len(out), "recordings": out}

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

        # Build the user's connectors once for this run.
        self._connectors = await asyncio.to_thread(build_connectors_for_user, self._current_user_id or "")
        connected = self._connectors.get("connected", [])
        self.think(f"Connected sources: {connected or 'none'}")

        # Fast path: nothing connected → don't burn LLM iterations.
        if not connected:
            answer = (
                "You don't have any data sources connected yet, so I can't look up live files, "
                "emails, or messages. Connect Google Drive, Gmail, Slack, Jira, or Zoom in KAIROS "
                "and I'll be able to answer questions about your real data."
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
        for _ in range(self.max_iterations):
            try:
                response = await self._chat_completion_with_fallback(
                    client=self._client, model=self.model, messages=messages,
                    temperature=0.2, max_tokens=900,
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
                        raise ValueError(f"Could not parse an Action from: {raw[:200]}")
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
                obs_str = json.dumps(observation, indent=2)[:2500]
                self.observe(f"{tool_name} → {str(observation)[:150]}")
                messages.append({"role": "user", "content": f"Observation from {tool_name}:\n{obs_str}"})

            except Exception as e:
                self.observe(f"ReAct step error: {e}")
                messages.append({"role": "user", "content": f"Error: {e}. Correct your format or pick another tool."})

        if not final_answer:
            final_answer = (
                "I couldn't complete the live lookup. Try asking more specifically, e.g. "
                "\"how many files are in my Drive?\" or \"show my last email\"."
            )

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

    async def evaluate_confidence(self, input_data: Any, output: Any) -> float:
        if isinstance(output, dict):
            ans = output.get("answer", "")
            if "couldn't complete" in ans or "don't have any data sources" in ans:
                return 0.3
            if output.get("sources"):
                return 0.9
            return 0.7
        return 0.5
