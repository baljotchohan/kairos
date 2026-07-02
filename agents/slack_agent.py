"""
Slack Agent — fetches raw messages from all Slack channels for the
orchestrator's central synthesis step (SynthesisAgent.extract_decisions()),
which is what actually turns raw content into DecisionNodes.
"""

from __future__ import annotations

from datetime import datetime

from config import config


from typing import Any

from agents.base_agent import BaseAgent, AgentTool

class SlackAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="slack_agent",
            description="Fetches raw Slack messages from channels and threads for decision extraction",
            max_iterations=1
        )

    def _register_tools(self):
        self.register_tool(AgentTool(
            name="fetch_slack_messages",
            description="Fetch raw slack messages for a lookback window.",
            handler=self.fetch
        ))

    async def execute(self, input_data: Any, **kwargs) -> Any:
        days = input_data if isinstance(input_data, int) else None
        return await self.fetch(lookback_days=days)

    def _get_slack_tokens(self, user_id: str | None = None) -> list[str]:
        tokens = []
        try:
            import sqlite3
            import json
            conn = sqlite3.connect(config.SQLITE_PATH)
            conn.row_factory = sqlite3.Row
            if user_id:
                rows = conn.execute(
                    "SELECT token_data FROM oauth_tokens WHERE service = 'slack' AND user_uid = ?",
                    (user_id,)
                ).fetchall()
            else:
                rows = conn.execute("SELECT token_data FROM oauth_tokens WHERE service = 'slack'").fetchall()

            for r in rows:
                try:
                    from core.token_crypto import decrypt_token_data
                    data = decrypt_token_data(r["token_data"])
                except Exception:
                    continue
                if data.get("bot_token") and not data.get("disconnected") and data.get("team_id") != "T-SIMULATED":
                    tokens.append(data["bot_token"])
            conn.close()
        except Exception as e:
            print(f"[SlackAgent] Database error while reading Slack tokens: {e}")

        # Only fall back to global env if no user_id is requested or no tokens at all are found
        if not tokens and not user_id and config.SLACK_BOT_TOKEN and config.SLACK_BOT_TOKEN != "xoxb-your-token":
            tokens = [config.SLACK_BOT_TOKEN]
        return tokens

    async def fetch(self, lookback_days: int = None, user_id: str | None = None) -> list[dict]:
        """Fetch raw message content from Slack to pass to the synthesis agent."""
        days = lookback_days or config.SLACK_LOOKBACK_DAYS
        tokens = self._get_slack_tokens(user_id=user_id)
        if not tokens:
            print(f"[SlackAgent] No Slack tokens configured for user {user_id} — skipping")
            return []

        from connectors.slack_connector import SlackConnector
        results = []
        for token in tokens:
            connector = SlackConnector(token=token)
            all_messages = await connector.fetch_all_with_threads(days_back=days)
            
            for msg in all_messages:
                text = msg.get("full_thread_text") or msg.get("text", "")
                if not text or len(text.strip()) < 5:
                    continue
                
                try:
                    date = datetime.utcfromtimestamp(float(msg.get("ts", "0"))).strftime("%Y-%m-%d")
                except (ValueError, TypeError):
                    date = datetime.utcnow().strftime("%Y-%m-%d")

                results.append({
                    "text": text,
                    "source": f"Slack #{msg.get('channel_name', 'unknown')}",
                    "source_url": msg.get("permalink", ""),
                    "date": date,
                })
        return results
