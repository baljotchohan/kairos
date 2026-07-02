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
                token = data.get("access_token") or data.get("api_key")
                if token and not data.get("disconnected"):
                    return token
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
