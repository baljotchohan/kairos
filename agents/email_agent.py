"""
Email Agent — fetches raw Gmail messages for the orchestrator's central
synthesis step (SynthesisAgent.extract_decisions()), which is what actually
turns raw content into DecisionNodes.
"""

from __future__ import annotations

from config import config


from typing import Any

from agents.base_agent import BaseAgent, AgentTool

class EmailAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="email_agent",
            description="Fetches raw email threads for decision extraction",
            max_iterations=1
        )

    def _register_tools(self):
        self.register_tool(AgentTool(
            name="fetch_emails",
            description="Fetch raw emails for a lookback window.",
            handler=self.fetch
        ))

    async def execute(self, input_data: Any, **kwargs) -> Any:
        days = input_data if isinstance(input_data, int) else None
        return await self.fetch(lookback_days=days)

    def _get_google_tokens(self, user_id: str | None = None) -> list[dict]:
        tokens = []
        try:
            import sqlite3
            import json
            conn = sqlite3.connect(config.SQLITE_PATH)
            conn.row_factory = sqlite3.Row
            if user_id:
                rows = conn.execute(
                    "SELECT token_data FROM oauth_tokens WHERE service = 'google' AND user_uid = ?",
                    (user_id,)
                ).fetchall()
            else:
                rows = conn.execute("SELECT token_data FROM oauth_tokens WHERE service = 'google'").fetchall()

            for r in rows:
                try:
                    from core.token_crypto import decrypt_token_data
                    data = decrypt_token_data(r["token_data"])
                except Exception:
                    continue
                if not data.get("disconnected") and data.get("refresh_token") != "sim-google-refresh-token":
                    tokens.append(data)
            conn.close()
        except Exception as e:
            print(f"[EmailAgent] Database error while reading Google tokens: {e}")

        # Fallback to server-side env if no user_id is requested or no tokens found
        if not tokens and not user_id and config.GOOGLE_REFRESH_TOKEN:
            tokens = [{
                "refresh_token": config.GOOGLE_REFRESH_TOKEN,
                "client_id": config.GOOGLE_CLIENT_ID,
                "client_secret": config.GOOGLE_CLIENT_SECRET,
            }]
        return tokens

    async def fetch(self, lookback_days: int = None, user_id: str | None = None) -> list[dict]:
        """Fetch raw email content from Gmail to pass to the synthesis agent."""
        days = lookback_days or config.EMAIL_LOOKBACK_DAYS
        tokens = self._get_google_tokens(user_id=user_id)
        if not tokens:
            print(f"[EmailAgent] No Google tokens configured for user {user_id} — skipping")
            return []

        from connectors.gmail_connector import GmailConnector
        results = []
        for t in tokens:
            connector = GmailConnector(
                refresh_token=t.get("refresh_token"),
                client_id=t.get("client_id"),
                client_secret=t.get("client_secret"),
            )
            emails = await connector.get_messages(days_back=days, max_results=200)
            
            for email_msg in emails:
                subject = email_msg.get("subject", "")
                body = email_msg.get("body", "")
                from_ = email_msg.get("from_", "")
                to = email_msg.get("to", "")
                date = email_msg.get("date", "")
                source_url = email_msg.get("source_url", "")
                
                full_text = f"Subject: {subject}\nFrom: {from_}\nTo: {to}\n\n{body}"
                if len(full_text.strip()) < 80:
                    continue
                
                text_lower = full_text.lower()
                decision_signals = [
                    "approved", "rejected", "decided", "decision", "going with",
                    "signed off", "contract", "agreement", "vendor", "budget",
                    "will not be", "moving forward", "we're choosing", "hired",
                    "terminated", "cancelled", "signed", "authorize", "authorised",
                ]
                if not any(sig in text_lower for sig in decision_signals):
                    continue

                results.append({
                    "text": full_text,
                    "source": "Email",
                    "source_url": source_url,
                    "date": date,
                })
        return results
