"""
Gmail connector — reads emails via Google Workspace API (async-wrapped).
Requires Google OAuth with gmail.readonly scope.
Returns gracefully empty list when credentials are missing.
"""

from __future__ import annotations

import asyncio
import base64
import email as email_lib
import re
from datetime import datetime, timedelta

from config import config


class GmailConnector:
    SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

    def __init__(self, refresh_token: str | None = None, client_id: str | None = None, client_secret: str | None = None):
        self.refresh_token = refresh_token or config.GOOGLE_REFRESH_TOKEN
        self.client_id = client_id or config.GOOGLE_CLIENT_ID
        self.client_secret = client_secret or config.GOOGLE_CLIENT_SECRET
        self._service = None

    def _build_service(self):
        """Build and return an authenticated Gmail service object."""
        if self._service:
            return self._service

        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build

        creds = Credentials(
            token=None,
            refresh_token=self.refresh_token,
            client_id=self.client_id,
            client_secret=self.client_secret,
            token_uri="https://oauth2.googleapis.com/token",
            scopes=self.SCOPES,
        )
        creds.refresh(Request())
        self._service = build("gmail", "v1", credentials=creds)
        return self._service

    # ── Public async API ───────────────────────────────────────────────────────

    async def get_messages(
        self,
        days_back: int,
        max_results: int = 200,
    ) -> list[dict]:
        """
        Fetch emails from the last `days_back` days.
        Returns list of dicts: {id, subject, body, from_, to, date, thread_id}.
        """
        if not self.refresh_token:
            return []

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, self._get_messages_sync, days_back, max_results
        )

    async def get_thread(self, thread_id: str) -> list[dict]:
        """
        Fetch all messages in an email thread.
        Returns list of parsed message dicts.
        """
        if not config.GOOGLE_REFRESH_TOKEN:
            return []

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._get_thread_sync, thread_id)

    async def get_recent(self, limit: int = 10, query: str | None = None) -> list[dict]:
        """
        List the most recent emails (NO decision-keyword filter), newest first.
        Returns lightweight summaries: {id, subject, from_, to, date, snippet, source_url}.
        Used for live "show my recent / last email" queries.
        """
        if not self.refresh_token:
            return []

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._get_recent_sync, limit, query)

    async def get_last(self, from_sender: str | None = None) -> dict | None:
        """Return the single most recent email (optionally from a given sender)."""
        q = f"from:{from_sender}" if from_sender else None
        recent = await self.get_recent(limit=1, query=q)
        return recent[0] if recent else None

    # ── Sync internals (run in executor) ──────────────────────────────────────

    def _get_messages_sync(self, days_back: int, max_results: int) -> list[dict]:
        svc = self._build_service()
        cutoff = (datetime.utcnow() - timedelta(days=days_back)).strftime("%Y/%m/%d")

        # Search for decision-relevant emails + recency filter
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
                        userId="me",
                        q=query,
                        maxResults=min(100, max_results - len(results)),
                        pageToken=page_token,
                    ).execute()
                    batch = resp.get("messages", [])
                    for raw in batch:
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
                    if not page_token or not batch:
                        break
                except Exception as e:
                    print(f"[GmailConnector] search error: {e}")
                    break

        print(f"[GmailConnector] Fetched {len(results)} emails")
        return results

    def _get_thread_sync(self, thread_id: str) -> list[dict]:
        svc = self._build_service()
        try:
            thread = svc.users().threads().get(userId="me", id=thread_id, format="full").execute()
            return [
                self._parse_message(msg)
                for msg in thread.get("messages", [])
                if msg
            ]
        except Exception as e:
            print(f"[GmailConnector] get_thread error: {e}")
            return []

    def _get_recent_sync(self, limit: int, query: str | None) -> list[dict]:
        svc = self._build_service()
        limit = max(1, min(limit, 50))
        try:
            resp = svc.users().messages().list(
                userId="me",
                q=query or "in:inbox",
                maxResults=limit,
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

    def _parse_summary(self, raw: dict) -> dict:
        """Lightweight parse for listings — headers + snippet, no body fetch."""
        headers = {
            h["name"]: h["value"]
            for h in raw.get("payload", {}).get("headers", [])
        }
        date_str = headers.get("Date", "")
        try:
            dt = email_lib.utils.parsedate_to_datetime(date_str)
            date = dt.strftime("%Y-%m-%d")
        except Exception:
            date = date_str[:10] if date_str else ""
        thread_id = raw.get("threadId", "")
        return {
            "id": raw.get("id", ""),
            "subject": headers.get("Subject", "(no subject)"),
            "from_": headers.get("From", "unknown"),
            "to": headers.get("To", ""),
            "date": date,
            "snippet": raw.get("snippet", ""),
            "source_url": f"https://mail.google.com/mail/u/0/#all/{thread_id}",
        }

    def _fetch_full_message(self, svc, msg_id: str):
        try:
            return svc.users().messages().get(userId="me", id=msg_id, format="full").execute()
        except Exception as e:
            print(f"[GmailConnector] fetch message {msg_id} error: {e}")
            return None

    def _parse_message(self, raw: dict) -> dict:
        """Parse a Gmail API message into a clean dict."""
        headers = {
            h["name"]: h["value"]
            for h in raw.get("payload", {}).get("headers", [])
        }
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

        # Collect unique participants
        participants = list({
            p.strip()
            for p in (from_ + "," + to).split(",")
            if p.strip()
        })

        return {
            "id": msg_id,
            "subject": subject,
            "body": body[:8000],
            "from_": from_,
            "to": to,
            "date": date,
            "thread_id": thread_id,
            "participants": participants,
            "source_url": f"https://mail.google.com/mail/u/0/#all/{thread_id}",
        }

    def _extract_body(self, payload: dict, depth: int = 0) -> str:
        """Recursively extract plain text body from MIME payload."""
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
