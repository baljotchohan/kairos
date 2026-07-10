"""
KAIROS Slack Bot — real-time @mention responder using Slack Bolt (async).

Listens for @KAIROS mentions via Socket Mode and replies in-thread
with an answer from KAIROS organizational memory.

Requirements:
  SLACK_APP_TOKEN  — xapp-... (App-level token with connections:write scope)
  SLACK_BOT_TOKEN  — xoxb-... (OAuth bot token, stored in DB or .env)
"""

from __future__ import annotations

import re
import sqlite3

from config import config
from core.token_crypto import decrypt_token_data


class SlackBot:
    def __init__(self, orchestrator=None):
        self.orchestrator = orchestrator
        self._bolt_app = None
        self._handler = None
        # team_id -> (bot_token, user_uid, owner_slack_id). A single Socket Mode
        # connection (one SLACK_APP_TOKEN) receives app_mention events for EVERY
        # workspace this Slack app is installed to, so each event must be routed
        # using ITS OWN team's bot token and user_uid — never a single hardcoded
        # "owner". owner_slack_id is the Slack member ID of the person who
        # connected this workspace (authed_user.id at OAuth time); the bot answers
        # from KAIROS memory ONLY for that person, so other workspace members
        # can't read the owner's private cross-source memory. See _handle_mention.
        self._team_creds: dict[str, tuple[str, str, str]] = {}
        # team_id -> bot user id, so self-mention filtering works per-workspace too
        self._bot_user_ids: dict[str, str] = {}

    # ── Token helpers ──────────────────────────────────────────────────────────

    def _get_app_token(self) -> str:
        t = config.SLACK_APP_TOKEN or ""
        return t if (t.startswith("xapp-") and len(t) > 20) else ""

    def _load_team_creds(self) -> dict[str, tuple[str, str, str]]:
        """Build team_id -> (bot_token, user_uid, owner_slack_id) for every
        connected Slack workspace. owner_slack_id is "" for legacy connections
        made before it was captured — those fail closed in _handle_mention."""
        team_creds: dict[str, tuple[str, str, str]] = {}
        try:
            conn = sqlite3.connect(config.SQLITE_PATH)
            rows = conn.execute(
                "SELECT token_data, user_uid FROM oauth_tokens "
                "WHERE service = 'slack' AND user_uid IS NOT NULL AND user_uid != ''"
            ).fetchall()
            conn.close()
            for row in rows:
                data = decrypt_token_data(row[0])
                # "disconnected" is a flag inside the encrypted token_data JSON, not
                # a DB column (see api/routes/oauth.py's disconnect_service) — must
                # be checked post-decrypt.
                if data.get("disconnected"):
                    continue
                t = data.get("bot_token", "")
                team_id = data.get("team_id", "")
                owner_slack_id = data.get("authed_user_id", "") or ""
                uid = row[1]
                if t.startswith("xoxb-") and len(t) > 30 and uid and team_id:
                    team_creds[team_id] = (t, uid, owner_slack_id)
        except Exception:
            pass
        return team_creds

    def is_configured(self) -> bool:
        return bool(self._get_app_token() and (self._team_creds or config.SLACK_BOT_TOKEN))

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    async def start(self):
        app_token = self._get_app_token()
        self._team_creds = self._load_team_creds()

        if not app_token:
            print("[SlackBot] SLACK_APP_TOKEN not set — mention responses disabled.")
            return
        if not self._team_creds:
            print("[SlackBot] No connected Slack workspace found — mention responses disabled.")
            return

        from slack_bolt.async_app import AsyncApp
        from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
        from slack_sdk.web.async_client import AsyncWebClient

        # Bolt needs ONE token to construct the app and drive the Socket Mode
        # handshake, but it is never used to post replies — _handle_mention always
        # builds a fresh AsyncWebClient scoped to the mentioning event's own team.
        bootstrap_token = next(iter(self._team_creds.values()))[0]
        self._bolt_app = AsyncApp(token=bootstrap_token, ignoring_self_events_enabled=True)

        for team_id, (bot_token, _uid, _owner) in self._team_creds.items():
            try:
                auth = await AsyncWebClient(token=bot_token).auth_test()
                self._bot_user_ids[team_id] = auth["user_id"]
                print(f"[SlackBot] Authenticated as @{auth['user']} in team {team_id}")
            except Exception as e:
                print(f"[SlackBot] auth_test failed for team {team_id}: {e}")

        # Register the app_mention handler
        @self._bolt_app.event("app_mention")
        async def handle_mention(event, context, **_):
            await self._handle_mention(event, context)

        self._handler = AsyncSocketModeHandler(self._bolt_app, app_token)
        await self._handler.connect_async()
        print(f"[SlackBot] ✅ Socket Mode (Bolt) connected — listening for @KAIROS mentions across {len(self._team_creds)} workspace(s)")

    async def stop(self):
        if self._handler:
            try:
                await self._handler.disconnect_async()
            except Exception:
                pass
        print("[SlackBot] Disconnected")

    # ── Mention handler ────────────────────────────────────────────────────────

    async def _handle_mention(self, event: dict, context: dict):
        # Resolve which connected KAIROS user owns THIS event's workspace — never
        # a single shared/default user. A mention from a workspace we don't have
        # a KAIROS connection for is dropped rather than answered from someone
        # else's memory.
        team_id = (context or {}).get("team_id") or event.get("team", "")
        bot_token, user_uid, owner_slack_id = self._team_creds.get(team_id, (None, None, None))
        if not bot_token:
            # The workspace may have connected after the bot started — refresh once.
            self._team_creds = self._load_team_creds()
            bot_token, user_uid, owner_slack_id = self._team_creds.get(team_id, (None, None, None))
        if not bot_token:
            print(f"[SlackBot] Ignoring mention from unrecognized team_id={team_id!r}")
            return

        from slack_sdk.web.async_client import AsyncWebClient
        client = AsyncWebClient(token=bot_token)

        bot_user_id = self._bot_user_ids.get(team_id)
        if bot_user_id is None:
            try:
                auth = await client.auth_test()
                bot_user_id = auth["user_id"]
                self._bot_user_ids[team_id] = bot_user_id
            except Exception:
                bot_user_id = None

        # Ignore self-mentions
        if event.get("bot_id") or (bot_user_id and event.get("user") == bot_user_id):
            return

        channel = event.get("channel", "")
        thread_ts = event.get("thread_ts") or event.get("ts")
        raw_text = event.get("text", "")
        user = event.get("user", "unknown")

        # ── Access control (fail-closed) ────────────────────────────────────────
        # KAIROS memory is private to the person who connected THIS workspace.
        # Their Slack member ID (owner_slack_id, = authed_user.id at OAuth time)
        # is the only identity allowed to query it via @mention — otherwise ANY
        # workspace member could read the owner's full cross-source private memory
        # (Gmail/Drive/Jira/GitHub/Notion decisions, not just Slack) just by
        # mentioning the bot. A missing owner_slack_id means a legacy connection
        # made before we captured it: we can't verify the asker is the owner, so
        # we refuse rather than risk the leak (owner reconnects Slack once to fix).
        if not owner_slack_id or user != owner_slack_id:
            reason = "unverified legacy connection" if not owner_slack_id else f"non-owner <@{user}>"
            print(f"[SlackBot] Refusing mention in team {team_id} ({reason}) — memory is owner-private.")
            try:
                frontend = (config.FRONTEND_URL or "").rstrip("/")
                connect_hint = f" Connect your own at {frontend}/integrations." if frontend else ""
                await AsyncWebClient(token=bot_token).chat_postMessage(
                    channel=channel,
                    thread_ts=thread_ts,
                    text=(
                        "🔒 KAIROS memory is private to the teammate who connected this "
                        "workspace, so I can't answer that here." + connect_hint
                        if owner_slack_id else
                        "🔒 This KAIROS Slack connection needs to be reconnected before I "
                        "can answer @mentions securely — the workspace owner can reconnect "
                        "Slack from KAIROS → Integrations."
                    ),
                )
            except Exception as e:
                print(f"[SlackBot] Could not post access-control notice: {e}")
            return

        question = re.sub(r"<@[A-Z0-9]+>", "", raw_text).strip()
        if not question:
            question = "What are the latest company decisions?"

        print(f"[SlackBot] Mention from <@{user}> in team {team_id}: {question[:100]}")

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

        # Query KAIROS — scoped to the mentioning workspace's own connected user
        try:
            answer, sources, confidence = await self._query_kairos(question, user_uid)
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

    async def _query_kairos(self, question: str, user_id: str) -> tuple[str, list, float]:
        if not self.orchestrator:
            return "KAIROS memory not initialized.", [], 0.0
        result = await self.orchestrator.query(question, user_id=user_id)
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
