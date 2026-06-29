"""
Gmail connector — full read access via Gmail API.
Requires Google OAuth with gmail.readonly scope.
"""

from __future__ import annotations

import asyncio
import base64
import email as email_lib
import re
from collections import Counter
from datetime import datetime, timedelta
from typing import Optional, Callable

from config import config


class GmailConnector:
    SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

    def __init__(
        self,
        access_token: str | None = None,
        refresh_token: str | None = None,
        client_id: str | None = None,
        client_secret: str | None = None,
        on_token_refresh: Callable[[dict], None] | None = None,
    ):
        self.access_token = access_token
        self.refresh_token = refresh_token or config.GOOGLE_REFRESH_TOKEN
        self.client_id = client_id or config.GOOGLE_CLIENT_ID
        self.client_secret = client_secret or config.GOOGLE_CLIENT_SECRET
        self.on_token_refresh = on_token_refresh
        self._service = None

    def _build_service(self):
        if self._service:
            return self._service
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
        creds = Credentials(
            token=self.access_token,
            refresh_token=self.refresh_token,
            client_id=self.client_id,
            client_secret=self.client_secret,
            token_uri="https://oauth2.googleapis.com/token",
            scopes=self.SCOPES,
        )
        if not creds.valid:
            creds.refresh(Request())
            self.access_token = creds.token
            if self.on_token_refresh:
                self.on_token_refresh({
                    "access_token": creds.token,
                    "refresh_token": self.refresh_token,
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                })
        self._service = build("gmail", "v1", credentials=creds)
        return self._service

    # ── Public async API ───────────────────────────────────────────────────────

    async def get_messages(self, days_back: int, max_results: int = 200) -> list[dict]:
        if not self.refresh_token:
            return []
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._get_messages_sync, days_back, max_results)

    async def get_recent(self, limit: int = 10, query: str | None = None) -> list[dict]:
        if not self.refresh_token:
            return []
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._get_recent_sync, limit, query)

    async def get_last(self, from_sender: str | None = None) -> Optional[dict]:
        q = f"from:{from_sender}" if from_sender else None
        recent = await self.get_recent(limit=1, query=q)
        return recent[0] if recent else None

    async def count_unread(self) -> dict:
        """Return unread counts: total + by label (inbox, promotions, social, etc.)."""
        if not self.refresh_token:
            return {"total_unread": 0}
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._count_unread_sync)

    async def get_thread_stats(self) -> dict:
        """Total thread/email count + top 5 senders."""
        if not self.refresh_token:
            return {}
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._thread_stats_sync)

    async def get_by_label(self, label: str = "INBOX", limit: int = 10) -> list[dict]:
        """Get emails in a specific label (INBOX, STARRED, SENT, IMPORTANT, SPAM, etc.)."""
        if not self.refresh_token:
            return []
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._get_by_label_sync, label.upper(), limit)

    async def get_sender_stats(self, days_back: int = 30, top_n: int = 10) -> list[dict]:
        """Return top N senders by email count over the past days_back days."""
        if not self.refresh_token:
            return []
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._sender_stats_sync, days_back, top_n)

    async def get_thread(self, thread_id: str) -> list[dict]:
        if not self.refresh_token:
            return []
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._get_thread_sync, thread_id)

    # ── Sync internals ─────────────────────────────────────────────────────────

    def _count_unread_sync(self) -> dict:
        svc = self._build_service()
        try:
            # Check per-label unread using labels.list + labels.get
            label_ids = ["INBOX", "CATEGORY_PROMOTIONS", "CATEGORY_SOCIAL", "CATEGORY_UPDATES", "CATEGORY_FORUMS", "STARRED", "IMPORTANT"]
            result = {"by_label": {}, "total_unread": 0}
            for lid in label_ids:
                try:
                    info = svc.users().labels().get(userId="me", id=lid).execute()
                    unread = info.get("messagesUnread", 0)
                    threads_unread = info.get("threadsUnread", 0)
                    friendly = lid.replace("CATEGORY_", "").title()
                    if unread > 0:
                        result["by_label"][friendly] = {"messages": unread, "threads": threads_unread}
                    if lid == "INBOX":
                        result["total_unread"] = unread
                        result["inbox_threads_unread"] = threads_unread
                except Exception:
                    pass
            # Also get profile for total message count
            try:
                profile = svc.users().getProfile(userId="me").execute()
                result["total_messages"] = profile.get("messagesTotal", 0)
                result["total_threads"] = profile.get("threadsTotal", 0)
                result["email_address"] = profile.get("emailAddress", "")
            except Exception:
                pass
            return result
        except Exception as e:
            print(f"[GmailConnector] count_unread error: {e}")
            return {"total_unread": 0}

    def _thread_stats_sync(self) -> dict:
        svc = self._build_service()
        try:
            profile = svc.users().getProfile(userId="me").execute()
            result = {
                "email_address": profile.get("emailAddress", ""),
                "total_messages": profile.get("messagesTotal", 0),
                "total_threads": profile.get("threadsTotal", 0),
            }
            # Get top senders from last 30 days
            result["top_senders"] = self._sender_stats_sync(30, 5)
            return result
        except Exception as e:
            print(f"[GmailConnector] thread_stats error: {e}")
            return {}

    def _sender_stats_sync(self, days_back: int, top_n: int) -> list[dict]:
        svc = self._build_service()
        cutoff = (datetime.utcnow() - timedelta(days=days_back)).strftime("%Y/%m/%d")
        try:
            resp = svc.users().messages().list(
                userId="me", q=f"after:{cutoff}", maxResults=500,
            ).execute()
            msgs = resp.get("messages", [])
            counter: Counter = Counter()
            for raw in msgs[:200]:
                meta = self._fetch_metadata(svc, raw["id"])
                if meta:
                    headers = {h["name"]: h["value"] for h in meta.get("payload", {}).get("headers", [])}
                    from_ = headers.get("From", "")
                    # Extract just the email address
                    m = re.search(r"<([^>]+)>", from_)
                    sender = m.group(1) if m else from_.strip()
                    if sender and "@" in sender:
                        counter[sender] += 1
            return [{"sender": s, "count": c} for s, c in counter.most_common(top_n)]
        except Exception as e:
            print(f"[GmailConnector] sender_stats error: {e}")
            return []

    def _get_by_label_sync(self, label: str, limit: int) -> list[dict]:
        svc = self._build_service()
        try:
            resp = svc.users().messages().list(
                userId="me", labelIds=[label], maxResults=limit,
            ).execute()
            out = []
            for raw in resp.get("messages", []):
                meta = self._fetch_metadata(svc, raw["id"])
                if meta:
                    out.append(self._parse_summary(meta))
            return out
        except Exception as e:
            print(f"[GmailConnector] get_by_label error ({label}): {e}")
            return []

    def _get_messages_sync(self, days_back: int, max_results: int) -> list[dict]:
        svc = self._build_service()
        cutoff = (datetime.utcnow() - timedelta(days=days_back)).strftime("%Y/%m/%d")
        queries = [
            f"after:{cutoff} (subject:decision OR subject:approved OR subject:rejected)",
            f"after:{cutoff} (subject:strategy OR subject:proposal OR subject:roadmap)",
            f"after:{cutoff} (subject:vendor OR subject:contract OR subject:budget OR subject:hire)",
            f"after:{cutoff}",
        ]
        seen: set[str] = set()
        results: list[dict] = []
        for query in queries:
            if len(results) >= max_results:
                break
            page_token = None
            while len(results) < max_results:
                try:
                    resp = svc.users().messages().list(
                        userId="me", q=query,
                        maxResults=min(100, max_results - len(results)),
                        pageToken=page_token,
                    ).execute()
                    for raw in resp.get("messages", []):
                        msg_id = raw["id"]
                        if msg_id in seen:
                            continue
                        seen.add(msg_id)
                        full = self._fetch_full_message(svc, msg_id)
                        if full:
                            parsed = self._parse_message(full)
                            if parsed and len(parsed.get("body", "")) > 20:
                                results.append(parsed)
                    page_token = resp.get("nextPageToken")
                    if not page_token or not resp.get("messages"):
                        break
                except Exception as e:
                    print(f"[GmailConnector] search error: {e}")
                    break
        return results

    def _get_thread_sync(self, thread_id: str) -> list[dict]:
        svc = self._build_service()
        try:
            thread = svc.users().threads().get(userId="me", id=thread_id, format="full").execute()
            return [self._parse_message(msg) for msg in thread.get("messages", []) if msg]
        except Exception as e:
            print(f"[GmailConnector] get_thread error: {e}")
            return []

    def _get_recent_sync(self, limit: int, query: str | None) -> list[dict]:
        svc = self._build_service()
        limit = max(1, min(limit, 50))
        try:
            resp = svc.users().messages().list(
                userId="me", q=query or "in:inbox", maxResults=limit,
            ).execute()
        except Exception as e:
            print(f"[GmailConnector] get_recent list error: {e}")
            return []
        out: list[dict] = []
        for raw in resp.get("messages", []):
            meta = self._fetch_metadata(svc, raw["id"])
            if meta:
                out.append(self._parse_summary(meta))
            if len(out) >= limit:
                break
        return out

    def _fetch_metadata(self, svc, msg_id: str):
        try:
            return svc.users().messages().get(
                userId="me", id=msg_id, format="metadata",
                metadataHeaders=["Subject", "From", "To", "Date"],
            ).execute()
        except Exception as e:
            print(f"[GmailConnector] fetch metadata {msg_id} error: {e}")
            return None

    def _fetch_full_message(self, svc, msg_id: str):
        try:
            return svc.users().messages().get(userId="me", id=msg_id, format="full").execute()
        except Exception as e:
            print(f"[GmailConnector] fetch message {msg_id} error: {e}")
            return None

    def _parse_summary(self, raw: dict) -> dict:
        headers = {h["name"]: h["value"] for h in raw.get("payload", {}).get("headers", [])}
        date_str = headers.get("Date", "")
        try:
            dt = email_lib.utils.parsedate_to_datetime(date_str)
            date = dt.strftime("%Y-%m-%d")
        except Exception:
            date = date_str[:10] if date_str else ""
        thread_id = raw.get("threadId", "")
        label_ids = raw.get("labelIds", [])
        is_unread = "UNREAD" in label_ids
        return {
            "id": raw.get("id", ""),
            "subject": headers.get("Subject", "(no subject)"),
            "from_": headers.get("From", "unknown"),
            "to": headers.get("To", ""),
            "date": date,
            "snippet": raw.get("snippet", ""),
            "unread": is_unread,
            "source_url": f"https://mail.google.com/mail/u/0/#all/{thread_id}",
        }

    def _parse_message(self, raw: dict) -> dict:
        headers = {h["name"]: h["value"] for h in raw.get("payload", {}).get("headers", [])}
        subject = headers.get("Subject", "(no subject)")
        from_ = headers.get("From", "unknown")
        to = headers.get("To", "")
        date_str = headers.get("Date", "")
        msg_id = raw.get("id", "")
        thread_id = raw.get("threadId", "")
        try:
            dt = email_lib.utils.parsedate_to_datetime(date_str)
            date = dt.strftime("%Y-%m-%d")
        except Exception:
            date = date_str[:10] if date_str else ""
        body = self._extract_body(raw.get("payload", {}))
        participants = list({p.strip() for p in (from_ + "," + to).split(",") if p.strip()})
        return {
            "id": msg_id,
            "subject": subject,
            "body": body[:8000],
            "from_": from_,
            "to": to,
            "date": date,
            "thread_id": thread_id,
            "participants": participants,
            "unread": "UNREAD" in raw.get("labelIds", []),
            "source_url": f"https://mail.google.com/mail/u/0/#all/{thread_id}",
        }

    def _extract_body(self, payload: dict, depth: int = 0) -> str:
        if depth > 6:
            return ""
        mime_type = payload.get("mimeType", "")
        body_data = payload.get("body", {}).get("data", "")
        if mime_type == "text/plain" and body_data:
            return base64.urlsafe_b64decode(body_data).decode("utf-8", errors="replace")
        for part in payload.get("parts", []):
            result = self._extract_body(part, depth + 1)
            if result:
                return result
        if mime_type == "text/html" and body_data:
            html = base64.urlsafe_b64decode(body_data).decode("utf-8", errors="replace")
            return re.sub(r"<[^>]+>", " ", html)
        return ""
