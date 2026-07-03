"""
Notion Agent — fetches raw pages and databases from Notion for the
orchestrator's central synthesis step (SynthesisAgent.extract_decisions()),
which is what actually turns raw content into DecisionNodes.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from agents.base_agent import BaseAgent, AgentTool
from config import config


class NotionAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="notion_agent",
            description="Fetches raw Notion pages and databases for decision extraction",
            max_iterations=1,
        )

    def _register_tools(self):
        self.register_tool(AgentTool(
            name="fetch_notion_pages",
            description="Fetch raw Notion pages for a lookback window.",
            handler=self.fetch,
        ))

    async def execute(self, input_data: Any, **kwargs) -> Any:
        days = input_data if isinstance(input_data, int) else None
        return await self.fetch(lookback_days=days)

    def _get_notion_key(self, user_id: str | None = None) -> str | None:
        """Per-user Notion token, FAIL-CLOSED like every other connector.

        When a user_id is given, only that user's own stored OAuth/API-key row
        may be used — never the global NOTION_API_KEY env var and never another
        user's row. Falling back to the env key here meant the background
        ingestion loop silently ingested the DEPLOYER's private Notion workspace
        into every active user's memory. The env key remains available only for
        the legacy no-user (local dev / single-tenant) path, matching the
        slack/email/drive agents' `not user_id` env-fallback pattern.
        """
        if user_id:
            try:
                import sqlite3
                conn = sqlite3.connect(config.SQLITE_PATH)
                conn.row_factory = sqlite3.Row
                row = conn.execute(
                    "SELECT token_data FROM oauth_tokens WHERE service = 'notion' AND user_uid = ?",
                    (user_id,),
                ).fetchone()
                conn.close()
                if row:
                    from core.token_crypto import decrypt_token_data
                    data = decrypt_token_data(row["token_data"])
                    token = data.get("access_token") or data.get("api_key")
                    if token and not data.get("disconnected"):
                        return token
            except Exception:
                pass
            return None  # fail closed: no per-user token → no Notion for this user

        # Legacy/no-user path only (local dev, single-tenant scripts).
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
