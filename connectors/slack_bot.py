"""
KAIROS Slack Bot — real-time @mention responder using Slack Bolt (async).

Listens for @KAIROS mentions via Socket Mode and replies in-thread
with an answer from KAIROS organizational memory.

Requirements:
  SLACK_APP_TOKEN  — xapp-... (App-level token with connections:write scope)
  SLACK_BOT_TOKEN  — xoxb-... (OAuth bot token, stored in DB or .env)
"""

from __future__ import annotations

import json
import re
import sqlite3
from typing import Optional

from config import config


class SlackBot:
    def __init__(self, orchestrator=None):
        self.orchestrator = orchestrator
        self._bolt_app = None
        self._handler = None
        self._bot_user_id: Optional[str] = None

    # ── Token helpers ──────────────────────────────────────────────────────────

    def _get_app_token(self) -> str:
        t = config.SLACK_APP_TOKEN or ""
        return t if (t.startswith("xapp-") and len(t) > 20) else ""

    def _get_bot_token(self) -> str:
        try:
            conn = sqlite3.connect(config.SQLITE_PATH)
            rows = conn.execute(
                "SELECT token_data FROM oauth_tokens WHERE service = 'slack'"
            ).fetchall()
            conn.close()
            for row in rows:
                data = json.loads(row[0])
                t = data.get("bot_token", "")
                if t.startswith("xoxb-") and len(t) > 30:
                    return t
        except Exception:
            pass
        t = config.SLACK_BOT_TOKEN or ""
        return t if (t.startswith("xoxb-") and len(t) > 30) else ""

    def is_configured(self) -> bool:
        return bool(self._get_app_token() and self._get_bot_token())

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    async def start(self):
        app_token = self._get_app_token()
        bot_token = self._get_bot_token()

        if not app_token:
            print("[SlackBot] SLACK_APP_TOKEN not set — mention responses disabled.")
            return
        if not bot_token:
            print("[SlackBot] No bot token found — mention responses disabled.")
            return

        from slack_bolt.async_app import AsyncApp
        from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler

        self._bolt_app = AsyncApp(token=bot_token, ignoring_self_events_enabled=True)

        # Fetch bot user ID to avoid reply loops
        client = self._bolt_app.client
        auth = await client.auth_test()
        self._bot_user_id = auth["user_id"]
        print(f"[SlackBot] Authenticated as @{auth['user']} (ID: {self._bot_user_id})")

        # Register the app_mention handler
        @self._bolt_app.event("app_mention")
        async def handle_mention(event, client, **_):
            await self._handle_mention(event, client)

        self._handler = AsyncSocketModeHandler(self._bolt_app, app_token)
        await self._handler.connect_async()
        print("[SlackBot] ✅ Socket Mode (Bolt) connected — listening for @KAIROS mentions")

    async def stop(self):
        if self._handler:
            try:
                await self._handler.disconnect_async()
            except Exception:
                pass
        print("[SlackBot] Disconnected")

    # ── Mention handler ────────────────────────────────────────────────────────

    async def _handle_mention(self, event: dict, client):
        # Ignore self-mentions
        if event.get("bot_id") or event.get("user") == self._bot_user_id:
            return

        channel = event.get("channel", "")
        thread_ts = event.get("thread_ts") or event.get("ts")
        raw_text = event.get("text", "")
        user = event.get("user", "unknown")

        question = re.sub(r"<@[A-Z0-9]+>", "", raw_text).strip()
        if not question:
            question = "What are the latest company decisions?"

        print(f"[SlackBot] Mention from <@{user}>: {question[:100]}")

        # Post thinking indicator and capture its ts for update
        thinking_ts = None
        try:
            r = await client.chat_postMessage(
                channel=channel,
                thread_ts=thread_ts,
                text="🧠 KAIROS is searching organizational memory...",
            )
            thinking_ts = r["ts"]
        except Exception as e:
            print(f"[SlackBot] Could not post thinking message: {e}")

        # Query KAIROS
        try:
            answer, sources, confidence = await self._query_kairos(question)
        except Exception as e:
            answer = f"KAIROS error: {e}"
            sources, confidence = [], 0.0
            print(f"[SlackBot] Query error: {e}")

        blocks = self._build_blocks(answer, sources, confidence)
        fallback = f"KAIROS: {answer[:200]}"

        if thinking_ts:
            try:
                await client.chat_update(
                    channel=channel,
                    ts=thinking_ts,
                    text=fallback,
                    blocks=blocks,
                )
                return
            except Exception:
                pass

        await client.chat_postMessage(
            channel=channel,
            thread_ts=thread_ts,
            text=fallback,
            blocks=blocks,
        )

    # ── KAIROS query ───────────────────────────────────────────────────────────

    async def _query_kairos(self, question: str) -> tuple[str, list, float]:
        if not self.orchestrator:
            return "KAIROS memory not initialized.", [], 0.0
        result = await self.orchestrator.query(question)
        return (
            result.get("answer", "KAIROS has no recorded decision on this topic."),
            result.get("sources", []),
            result.get("confidence", 0.0),
        )

    # ── Block Kit response ────────────────────────────────────────────────────

    def _build_blocks(self, answer: str, sources: list, confidence: float) -> list:
        blocks = [
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*🧠 KAIROS Answer*\n{answer}"},
            }
        ]

        if sources:
            lines = []
            for s in sources[:4]:
                title = s.get("title", "Unknown")
                src = s.get("source", "")
                date = s.get("date", "")
                url = s.get("source_url", "")
                lines.append(f"• <{url}|{title}>" if url else f"• *{title}* — {src} · {date}")
            blocks += [
                {"type": "divider"},
                {"type": "context", "elements": [{"type": "mrkdwn", "text": "*Sources:*\n" + "\n".join(lines)}]},
            ]

        pct = int(confidence * 100)
        icon = "🟢" if pct >= 70 else "🟡" if pct >= 40 else "🔴"
        blocks.append({
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": f"{icon} Confidence: {pct}%  |  _KAIROS Organizational Memory_"}],
        })
        return blocks
