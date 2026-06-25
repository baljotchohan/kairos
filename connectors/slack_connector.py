"""
Slack connector — reads messages from all channels using Slack Web API (async).
Requires SLACK_BOT_TOKEN with channels:history, channels:read, users:read scopes.
Returns gracefully empty list when credentials are missing.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

from config import config


class SlackConnector:
    def __init__(self, token: str = None):
        self._user_cache: dict[str, str] = {}
        self._token = token
        self._client = None

    def _get_client(self):
        if self._client is None:
            from slack_sdk.web.async_client import AsyncWebClient
            token = self._token
            if not token:
                raise ValueError(
                    "SlackConnector: no per-user token provided. "
                    "Pass the user's OAuth bot_token when constructing SlackConnector."
                )
            self._client = AsyncWebClient(token=token)
        return self._client

    # ── Public async API ───────────────────────────────────────────────────────

    async def get_channels(self) -> list[dict]:
        """Return all public/private channels the bot can see as {id, name} dicts."""
        if not self._token:
            return []

        client = self._get_client()
        channels = []
        cursor = None

        while True:
            try:
                kwargs: dict = {"types": "public_channel,private_channel", "limit": 200}
                if cursor:
                    kwargs["cursor"] = cursor
                resp = await client.conversations_list(**kwargs)
                for ch in resp.get("channels", []):
                    channels.append({"id": ch["id"], "name": ch.get("name", ch["id"])})
                cursor = resp.get("response_metadata", {}).get("next_cursor")
                if not cursor:
                    break
            except Exception as e:
                print(f"[SlackConnector] conversations_list error: {e}")
                break

        return channels

    async def get_messages(
        self,
        channel_id: str,
        days_back: int,
    ) -> list[dict]:
        """
        Fetch messages from a channel going back `days_back` days.
        Returns list of dicts: {ts, text, user, channel_name, permalink}.
        """
        if not self._token:
            return []

        client = self._get_client()
        cutoff = datetime.utcnow() - timedelta(days=days_back)
        oldest_ts = cutoff.timestamp()
        max_msgs = config.MAX_MESSAGES_PER_CHANNEL

        # Resolve channel name first
        channel_name = channel_id
        try:
            info = await client.conversations_info(channel=channel_id)
            channel_name = info["channel"].get("name", channel_id)
        except Exception:
            pass

        messages: list[dict] = []
        cursor = None

        while len(messages) < max_msgs:
            try:
                kwargs: dict = {
                    "channel": channel_id,
                    "oldest": str(oldest_ts),
                    "limit": min(200, max_msgs - len(messages)),
                }
                if cursor:
                    kwargs["cursor"] = cursor
                resp = await client.conversations_history(**kwargs)
                batch = resp.get("messages", [])

                for msg in batch:
                    if not msg.get("text"):
                        continue
                    ts = msg.get("ts", "0")
                    user_id = msg.get("user", "")
                    user_name = await self._resolve_user(user_id) if user_id else "unknown"

                    # Build a Slack deep-link permalink
                    ts_nodot = ts.replace(".", "")
                    permalink = f"https://slack.com/archives/{channel_id}/p{ts_nodot}"

                    messages.append({
                        "ts": ts,
                        "text": msg.get("text", ""),
                        "user": user_name,
                        "user_id": user_id,
                        "channel_id": channel_id,
                        "channel_name": channel_name,
                        "permalink": permalink,
                        "reply_count": msg.get("reply_count", 0),
                        "thread_ts": msg.get("thread_ts"),
                    })

                cursor = resp.get("response_metadata", {}).get("next_cursor")
                if not cursor or not batch:
                    break
            except Exception as e:
                err_str = str(e)
                if "not_in_channel" in err_str or "channel_not_found" in err_str:
                    break
                print(f"[SlackConnector] history error ({channel_id}): {e}")
                break

        return messages

    async def get_thread_replies(
        self, channel_id: str, thread_ts: str
    ) -> list[dict]:
        """Fetch all replies in a thread. Returns same shape as get_messages()."""
        if not self._token:
            return []

        client = self._get_client()
        try:
            resp = await client.conversations_replies(
                channel=channel_id,
                ts=thread_ts,
                limit=200,
            )
            raw = resp.get("messages", [])[1:]  # exclude the parent message
            replies = []
            for msg in raw:
                user_id = msg.get("user", "")
                user_name = await self._resolve_user(user_id) if user_id else "unknown"
                ts = msg.get("ts", "0")
                ts_nodot = ts.replace(".", "")
                replies.append({
                    "ts": ts,
                    "text": msg.get("text", ""),
                    "user": user_name,
                    "user_id": user_id,
                    "channel_id": channel_id,
                    "channel_name": "",
                    "permalink": f"https://slack.com/archives/{channel_id}/p{ts_nodot}",
                    "reply_count": 0,
                    "thread_ts": thread_ts,
                })
            return replies
        except Exception as e:
            print(f"[SlackConnector] thread_replies error: {e}")
            return []

    # ── Helpers ────────────────────────────────────────────────────────────────

    async def _resolve_user(self, user_id: str) -> str:
        """Resolve a Slack user ID to a display name (cached)."""
        if user_id in self._user_cache:
            return self._user_cache[user_id]
        client = self._get_client()
        try:
            resp = await client.users_info(user=user_id)
            name = (
                resp["user"].get("real_name")
                or resp["user"].get("profile", {}).get("display_name")
                or resp["user"].get("name")
                or user_id
            )
            self._user_cache[user_id] = name
            return name
        except Exception:
            self._user_cache[user_id] = user_id
            return user_id

    async def _resolve_mentions(self, text: str) -> str:
        """Resolve Slack user mentions in text to readable names (e.g., <@U12345> -> @Name)."""
        if not text:
            return text
        import re
        pattern = re.compile(r"<@(U[A-Z0-9]+)>")
        user_ids = pattern.findall(text)
        for uid in set(user_ids):
            name = await self._resolve_user(uid)
            text = text.replace(f"<@{uid}>", f"@{name}")
        return text

    async def fetch_all_with_threads(self, days_back: int) -> list[dict]:
        """
        Convenience: fetch all channels, all messages, expand threads.
        Returns list of message dicts with 'full_thread_text' set for threads.
        """
        channels = await self.get_channels()
        all_messages: list[dict] = []

        for ch in channels:
            ch_id = ch["id"]
            msgs = await self.get_messages(ch_id, days_back=days_back)

            for msg in msgs:
                # Resolve mentions in the main message text
                msg["text"] = await self._resolve_mentions(msg.get("text", ""))

                if msg.get("reply_count", 0) > 0 and msg.get("thread_ts"):
                    replies = await self.get_thread_replies(ch_id, msg["thread_ts"])
                    thread_parts = [f"{msg['user']}: {msg['text']}"]
                    for r in replies:
                        # Resolve mentions in reply texts
                        r_text = await self._resolve_mentions(r.get("text", ""))
                        thread_parts.append(f"{r['user']}: {r_text}")
                    msg["full_thread_text"] = "\n".join(thread_parts)
                else:
                    msg["full_thread_text"] = f"{msg['user']}: {msg['text']}"

                all_messages.append(msg)

        print(f"[SlackConnector] Fetched {len(all_messages)} messages from {len(channels)} channels")
        return all_messages
