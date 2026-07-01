"""
Notion Agent — fetches pages and databases from Notion and extracts decisions
using Fireworks AI. Returns DecisionNode objects for KairosMemory.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime
from typing import Any

from agents.base_agent import BaseAgent, AgentTool
from config import config
from core.fireworks import fireworks
from core.graph import DecisionNode


DECISION_SYSTEM = """You are KAIROS, an organizational memory AI. Extract important decisions from Notion pages and database entries.

Capture ANY of the following (be INCLUSIVE):
- A choice between alternatives ("we chose X over Y")
- An approval or sign-off ("approved to hire", "green-lit")
- A rejection or cancellation ("decided NOT to", "cancelled")
- A policy or direction statement ("going forward we will...")
- A strategic announcement ("we are launching X", "we will expand to Y")
- A technical architecture or product decision
- A hiring, vendor, budget, or partnership decision
- A project status or milestone decision ("we shipped X", "we paused Y")

Examples:
- "We're migrating from PostgreSQL to MongoDB." → IS a decision
- "Q3 OKR: Launch mobile app by September." → IS a decision (commitment)
- "Decided to pause the enterprise tier." → IS a decision

IGNORE: meeting agenda items with no resolution, pure templates/boilerplate, task lists with no decisions.

Return a JSON object:
{
  "is_decision": true or false,
  "title": "Short title (max 10 words)",
  "summary": "1-2 sentences describing the decision",
  "participants": ["Name1", "Name2"],
  "outcome": "What was decided or what happens next",
  "topics": ["topic1", "topic2"],
  "alternatives_considered": ["option A", "option B that was rejected"],
  "decision_maker": "Name of the person who made the final call"
}

If nothing important, return exactly: {"is_decision": false}
Return ONLY valid JSON. No markdown fences, no explanation."""


class NotionAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="notion_agent",
            description="Fetches Notion pages and databases and extracts decisions",
            max_iterations=1,
        )

    def _register_tools(self):
        self.register_tool(AgentTool(
            name="fetch_notion_pages",
            description="Fetch raw Notion pages for a lookback window.",
            handler=self.fetch,
        ))
        self.register_tool(AgentTool(
            name="extract_notion_decisions",
            description="Fetch and extract structured decision nodes from Notion.",
            handler=self.run,
        ))

    async def execute(self, input_data: Any, **kwargs) -> Any:
        days = input_data if isinstance(input_data, int) else None
        return await self.run(lookback_days=days)

    def _get_notion_key(self, user_id: str | None = None) -> str | None:
        # Per-user Notion tokens stored via OAuth (future). For now, use global env key.
        try:
            import sqlite3
            conn = sqlite3.connect(config.SQLITE_PATH)
            conn.row_factory = sqlite3.Row
            query = (
                "SELECT token_data FROM oauth_tokens WHERE service = 'notion' AND user_uid = ?"
                if user_id
                else "SELECT token_data FROM oauth_tokens WHERE service = 'notion'"
            )
            params = (user_id,) if user_id else ()
            row = conn.execute(query, params).fetchone()
            conn.close()
            if row:
                from core.token_crypto import decrypt_token_data
                data = decrypt_token_data(row["token_data"])
                if data.get("api_key") and not data.get("disconnected"):
                    return data["api_key"]
        except Exception:
            pass

        # Fall back to global env key
        if config.NOTION_API_KEY:
            return config.NOTION_API_KEY
        return None

    async def fetch(self, lookback_days: int = None, user_id: str | None = None) -> list[dict]:
        """Fetch raw Notion page content to pass to synthesis agent."""
        days = lookback_days or 30
        api_key = self._get_notion_key(user_id=user_id)
        if not api_key:
            print(f"[NotionAgent] No Notion API key for user {user_id} — skipping")
            return []

        from connectors.notion_connector import NotionConnector
        connector = NotionConnector(api_key=api_key)
        items = await connector.fetch_all(days_back=days)

        results = []
        for item in items:
            text = item.get("text", "")
            if not text.strip():
                continue
            results.append({
                "text": text,
                "source": item.get("source", "Notion"),
                "source_url": item.get("url", ""),
                "date": item.get("date", datetime.utcnow().strftime("%Y-%m-%d")),
            })
        return results

    async def run(self, lookback_days: int = None, user_id: str | None = None) -> list[DecisionNode]:
        """Fetch all Notion content, classify via Fireworks AI, return DecisionNodes."""
        days = lookback_days or 30
        api_key = self._get_notion_key(user_id=user_id)
        if not api_key:
            print(f"[NotionAgent] No Notion API key for user {user_id} — skipping")
            return []

        print(f"[NotionAgent] Starting ingestion ({days} days lookback) for user {user_id}")

        from connectors.notion_connector import NotionConnector
        connector = NotionConnector(api_key=api_key)
        items = await connector.fetch_all(days_back=days)
        print(f"[NotionAgent] Processing {len(items)} Notion items")

        decisions: list[DecisionNode] = []
        for item in items:
            nodes = await self._extract_decisions(item)
            for node in nodes:
                if user_id:
                    node.user_id = user_id
            decisions.extend(nodes)

        print(f"[NotionAgent] Extracted {len(decisions)} decisions from Notion")
        return decisions

    async def _extract_decisions(self, item: dict) -> list[DecisionNode]:
        text = item.get("text", "")
        if not text or len(text.strip()) < 30:
            return []

        title = item.get("title", "Untitled")
        url = item.get("url", "")
        date = item.get("date", datetime.utcnow().strftime("%Y-%m-%d"))
        source = item.get("source", "Notion")

        prompt = (
            f"Source: {source}\n"
            f"Title: {title}\n"
            f"Date: {date}\n"
            f"Content:\n---\n{text[:4000]}\n---\n\n"
            f"Is there a decision here? Extract it if so."
        )

        try:
            raw = await fireworks.complete(prompt, system=DECISION_SYSTEM, max_tokens=600)
            raw = raw.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
                raw = raw.strip()
            data = json.loads(raw)
        except Exception as e:
            print(f"[NotionAgent] extraction error for '{title}': {e}")
            return []

        if not data.get("is_decision"):
            return []

        extracted_title = data.get("title", "").strip() or title
        summary = data.get("summary", "").strip()
        if not extracted_title or not summary:
            return []

        fingerprint = url or f"notion:{item.get('id', '')}:{extracted_title}"
        node_id = str(uuid.UUID(hashlib.md5(fingerprint.encode()).hexdigest()))

        node = DecisionNode(
            id=node_id,
            title=extracted_title,
            summary=summary,
            date=date,
            participants=data.get("participants", []),
            source=source,
            source_url=url,
            topics=data.get("topics", []),
            outcome=data.get("outcome", ""),
            raw_text=text[:2000],
            metadata={
                "alternatives_considered": data.get("alternatives_considered", []),
                "decision_maker": data.get("decision_maker", ""),
                "notion_title": title,
            },
        )
        return [node]
