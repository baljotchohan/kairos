"""
Slack Agent — fetches messages from all Slack channels and uses Fireworks AI
to classify and extract decisions from them.

Returns a list of DecisionNode objects ready to be stored in KairosMemory.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime

from config import config
from core.fireworks import fireworks
from core.graph import DecisionNode


DECISION_SYSTEM = """You are KAIROS, an organizational memory AI. Extract important moments from Slack messages.

Capture ANY of the following (be INCLUSIVE):
- A choice between alternatives ("we chose X over Y")
- An approval or sign-off ("approved to hire", "green-lit")
- A rejection or cancellation ("decided NOT to", "cancelled")
- A policy or direction statement ("going forward we will...")
- A strategic announcement ("we are launching X", "we will expand to Y in 2027")
- A company plan, commitment, or milestone ("we're building X", "raising a round")
- A technical architecture choice
- A hiring, vendor, budget, or partnership decision

Examples:
- "We're going with AWS over GCP." → IS a decision
- "Approved to hire two senior engineers in Q3." → IS a decision
- "We are launching a new startup in 2027." → IS a decision (strategic plan)
- "We will expand to the US market next year." → IS a decision (commitment)
- "We decided NOT to use microservices." → IS a decision

IGNORE ONLY: pure greetings, emoji-only messages, and pure scheduling ("when is the standup?").

Return a JSON object:
{
  "is_decision": true or false,
  "title": "Short title (max 10 words)",
  "summary": "1-2 sentences describing the decision or announcement",
  "participants": ["Name1", "Name2"],
  "outcome": "What was decided or what happens next",
  "topics": ["topic1", "topic2"],
  "alternatives_considered": ["option A", "option B that was rejected"],
  "decision_maker": "Name of the person who made/approved the final call"
}

If the content has nothing important, return exactly: {"is_decision": false}
Return ONLY valid JSON. No markdown fences, no explanation."""


from typing import Any

from agents.base_agent import BaseAgent, AgentTool

class SlackAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="slack_agent",
            description="Fetches and extracts decisions from Slack channels and threads",
            max_iterations=1
        )

    def _register_tools(self):
        self.register_tool(AgentTool(
            name="fetch_slack_messages",
            description="Fetch raw slack messages for a lookback window.",
            handler=self.fetch
        ))
        self.register_tool(AgentTool(
            name="extract_slack_decisions",
            description="Fetch and extract structured decision nodes from Slack.",
            handler=self.run
        ))

    async def execute(self, input_data: Any, **kwargs) -> Any:
        days = input_data if isinstance(input_data, int) else None
        return await self.run(lookback_days=days)

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
                data = json.loads(r["token_data"])
                if data.get("bot_token") and not data.get("disconnected"):
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

    async def run(self, lookback_days: int = None, user_id: str | None = None) -> list[DecisionNode]:
        """
        Fetch all Slack messages for the configured lookback window,
        classify each batch via Fireworks AI, and return extracted DecisionNodes.
        """
        days = lookback_days or config.SLACK_LOOKBACK_DAYS
        tokens = self._get_slack_tokens(user_id=user_id)
        if not tokens:
            print(f"[SlackAgent] No Slack tokens configured for user {user_id} — skipping")
            return []

        print(f"[SlackAgent] Starting ingestion ({days} days lookback) for user {user_id}")

        from connectors.slack_connector import SlackConnector
        decisions: list[DecisionNode] = []

        for token in tokens:
            connector = SlackConnector(token=token)
            all_messages = await connector.fetch_all_with_threads(days_back=days)
            print(f"[SlackAgent] Processing {len(all_messages)} messages from workspace")

            # Process messages in batches of 10 to keep prompts manageable
            batch_size = 10
            for batch_start in range(0, len(all_messages), batch_size):
                batch = all_messages[batch_start: batch_start + batch_size]
                extracted = await self._extract_decisions_from_batch(batch)
                for node in extracted:
                    if user_id:
                        node.user_id = user_id
                decisions.extend(extracted)

        print(f"[SlackAgent] Extracted {len(decisions)} decisions")
        return decisions

    async def _extract_decisions_from_batch(
        self, messages: list[dict]
    ) -> list[DecisionNode]:
        """
        For each message in the batch, call Fireworks AI to determine if it
        is a decision and extract structured data. Returns DecisionNode list.
        """
        results: list[DecisionNode] = []

        for msg in messages:
            text = msg.get("full_thread_text") or msg.get("text", "")
            if not text or len(text.strip()) < 30:
                continue

            channel_name = msg.get("channel_name", "unknown")
            user = msg.get("user", "unknown")
            ts = msg.get("ts", "0")
            permalink = msg.get("permalink", "")

            # Convert Slack timestamp to ISO date
            try:
                date = datetime.utcfromtimestamp(float(ts)).strftime("%Y-%m-%d")
            except (ValueError, TypeError):
                date = datetime.utcnow().strftime("%Y-%m-%d")

            prompt = (
                f"Slack channel: #{channel_name}\n"
                f"Posted by: {user}\n"
                f"Date: {date}\n"
                f"Message:\n---\n{text[:3000]}\n---\n\n"
                f"Is this a decision? Extract it if so."
            )

            try:
                raw = await fireworks.complete(prompt, system=DECISION_SYSTEM, max_tokens=600)
                raw = raw.strip()

                # Strip markdown code fences if present
                if raw.startswith("```"):
                    raw = raw.split("```")[1]
                    if raw.startswith("json"):
                        raw = raw[4:]
                    raw = raw.strip()

                data = json.loads(raw)
            except Exception as e:
                print(f"[SlackAgent] extraction error for msg in #{channel_name}: {e}")
                continue

            if not data.get("is_decision"):
                continue

            title = data.get("title", "").strip()
            summary = data.get("summary", "").strip()
            if not title or not summary:
                continue

            # Deterministic ID from permalink (or text hash) prevents duplicate
            # entries when ingestion runs multiple times over the same messages
            fingerprint = permalink or f"{channel_name}:{ts}:{title}"
            node_id = str(uuid.UUID(hashlib.md5(fingerprint.encode()).hexdigest()))

            node = DecisionNode(
                id=node_id,
                title=title,
                summary=summary,
                date=date,
                participants=data.get("participants", [user]),
                source=f"Slack #{channel_name}",
                source_url=permalink,
                topics=data.get("topics", []),
                outcome=data.get("outcome", ""),
                raw_text=text[:2000],
                metadata={
                    "alternatives_considered": data.get("alternatives_considered", []),
                    "decision_maker": data.get("decision_maker", user),
                    "channel": channel_name,
                },
            )
            results.append(node)

        return results
