"""
GitHub Agent — fetches raw pull requests and issues from GitHub for the
orchestrator's central synthesis step (SynthesisAgent.extract_decisions()),
which is what actually turns raw content into DecisionNodes.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from agents.base_agent import BaseAgent, AgentTool
from config import config


class GitHubAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="github_agent",
            description="Fetches raw GitHub PRs and issues for decision extraction",
            max_iterations=1,
        )

    def _register_tools(self):
        self.register_tool(AgentTool(
            name="fetch_github_activity",
            description="Fetch raw GitHub PRs and issues for a lookback window.",
            handler=self.fetch,
        ))

    async def execute(self, input_data: Any, **kwargs) -> Any:
        days = input_data if isinstance(input_data, int) else None
        return await self.fetch(lookback_days=days)

    def _get_github_token(self, user_id: str | None = None) -> str | None:
        """Per-user GitHub token, fail-closed. Unlike Jira/Zoom, GitHub has no
        global/shared credential in this deployment — a missing per-user token
        always means "not connected for this user", never a fallback."""
        if not user_id:
            return None
        try:
            import sqlite3
            conn = sqlite3.connect(config.SQLITE_PATH)
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT token_data FROM oauth_tokens WHERE service = 'github' AND user_uid = ?",
                (user_id,),
            ).fetchone()
            conn.close()
            if row:
                from core.token_crypto import decrypt_token_data
                data = decrypt_token_data(row["token_data"])
                token = data.get("access_token")
                if token and not data.get("disconnected"):
                    return token
        except Exception:
            pass
        return None

    async def fetch(self, lookback_days: int = None, user_id: str | None = None) -> list[dict]:
        """Fetch raw GitHub PR/issue content to pass to the synthesis agent."""
        days = lookback_days or 30
        token = self._get_github_token(user_id=user_id)
        if not token:
            print(f"[GitHubAgent] No GitHub token for user {user_id} — skipping")
            return []

        from connectors.github_connector import GitHubConnector
        connector = GitHubConnector(access_token=token)
        items = await connector.fetch_all(days_back=days)

        results = []
        for item in items:
            text = item.get("text", "")
            if not text.strip():
                continue
            results.append({
                "text": text,
                "source": item.get("source", "GitHub"),
                "source_url": item.get("url", ""),
                "date": item.get("date", datetime.utcnow().strftime("%Y-%m-%d")),
            })
        return results
