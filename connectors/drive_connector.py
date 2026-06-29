"""
Google Drive connector — reads documents, meeting notes, proposals, specs.
Requires Google OAuth with drive.readonly + documents.readonly scopes.
Returns gracefully empty list when credentials are missing.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

from typing import Callable

from config import config


class DriveConnector:
    SCOPES = [
        "https://www.googleapis.com/auth/drive.readonly",
    ]

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
        self._drive = None
        self._docs = None

    def _build_services(self):
        """Build and return authenticated Drive + Docs service objects."""
        if self._drive and self._docs:
            return self._drive, self._docs

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
        self._drive = build("drive", "v3", credentials=creds)
        self._docs = build("docs", "v1", credentials=creds)
        return self._drive, self._docs

    # ── Public async API ───────────────────────────────────────────────────────

    async def list_files(self, days_back: int) -> list[dict]:
        """
        List recently modified Google Docs.
        Returns list of dicts: {id, name, mimeType, modifiedTime, webViewLink}.
        """
        if not self.refresh_token:
            return []

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._list_files_sync, days_back)

    async def get_file_content(self, file_id: str, mime_type: str) -> str:
        """
        Export a Drive file and return its plain-text content.
        Handles Google Docs natively; exports other types via Drive export API.
        """
        if not self.refresh_token:
            return ""

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._get_content_sync, file_id, mime_type)

    async def count_files(self) -> dict:
        """
        Count non-trashed files in the user's Drive (capped for speed).
        Returns {total, capped, by_type} — by_type maps a friendly type → count.
        Used for live "how many files do I have?" queries.
        """
        if not self.refresh_token:
            return {"total": 0, "capped": False, "by_type": {}}

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._count_files_sync)

    async def list_all_files(self, limit: int = 20, name_query: str | None = None) -> list[dict]:
        """
        List the user's most recently modified files of ANY type (not just Docs),
        optionally filtered by name. Returns dicts with
        {id, name, mimeType, friendlyType, modifiedTime, webViewLink, owners}.
        """
        if not self.refresh_token:
            return []

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._list_all_files_sync, limit, name_query)

    # ── Sync internals (run in executor) ──────────────────────────────────────

    def _list_files_sync(self, days_back: int) -> list[dict]:
        drive, _ = self._build_services()
        cutoff = (datetime.utcnow() - timedelta(days=days_back)).isoformat() + "Z"

        # Priority: Google Docs (meeting notes, ADRs, proposals, postmortems)
        query = (
            f"(mimeType='application/vnd.google-apps.document' "
            f"OR mimeType='application/vnd.google-apps.spreadsheet') "
            f"AND modifiedTime > '{cutoff}' "
            f"AND trashed = false"
        )

        files: list[dict] = []
        page_token = None

        while len(files) < 100:
            try:
                resp = drive.files().list(
                    q=query,
                    fields="nextPageToken, files(id, name, mimeType, modifiedTime, webViewLink, owners)",
                    pageSize=min(100, 100 - len(files)),
                    pageToken=page_token,
                ).execute()
                files.extend(resp.get("files", []))
                page_token = resp.get("nextPageToken")
                if not page_token:
                    break
            except Exception as e:
                print(f"[DriveConnector] list_files error: {e}")
                break

        return files

    def _count_files_sync(self, max_count: int = 5000) -> dict:
        drive, _ = self._build_services()
        total = 0
        by_type: dict[str, int] = {}
        page_token = None
        capped = False
        try:
            while True:
                resp = drive.files().list(
                    q="trashed = false",
                    fields="nextPageToken, files(mimeType)",
                    pageSize=1000,
                    pageToken=page_token,
                ).execute()
                batch = resp.get("files", [])
                total += len(batch)
                for f in batch:
                    ft = self._friendly_type(f.get("mimeType", ""))
                    by_type[ft] = by_type.get(ft, 0) + 1
                page_token = resp.get("nextPageToken")
                if not page_token:
                    break
                if total >= max_count:
                    capped = True
                    break
        except Exception as e:
            print(f"[DriveConnector] count_files error: {e}")
        return {"total": total, "capped": capped, "by_type": by_type}

    def _list_all_files_sync(self, limit: int, name_query: str | None) -> list[dict]:
        drive, _ = self._build_services()
        q = "trashed = false"
        if name_query:
            safe = name_query.replace("\\", "\\\\").replace("'", "\\'")
            q += f" and name contains '{safe}'"

        files: list[dict] = []
        page_token = None
        try:
            while len(files) < limit:
                resp = drive.files().list(
                    q=q,
                    orderBy="modifiedTime desc",
                    fields="nextPageToken, files(id, name, mimeType, modifiedTime, webViewLink, owners)",
                    pageSize=min(100, limit - len(files)),
                    pageToken=page_token,
                ).execute()
                files.extend(resp.get("files", []))
                page_token = resp.get("nextPageToken")
                if not page_token:
                    break
        except Exception as e:
            print(f"[DriveConnector] list_all_files error: {e}")

        for f in files:
            f["friendlyType"] = self._friendly_type(f.get("mimeType", ""))
        return files[:limit]

    @staticmethod
    def _friendly_type(mime: str) -> str:
        mapping = {
            "application/vnd.google-apps.document": "Google Doc",
            "application/vnd.google-apps.spreadsheet": "Google Sheet",
            "application/vnd.google-apps.presentation": "Google Slides",
            "application/vnd.google-apps.form": "Google Form",
            "application/vnd.google-apps.folder": "Folder",
            "application/pdf": "PDF",
            "application/zip": "Archive",
            "text/plain": "Text",
        }
        if mime in mapping:
            return mapping[mime]
        if mime.startswith("image/"):
            return "Image"
        if mime.startswith("video/"):
            return "Video"
        if mime.startswith("audio/"):
            return "Audio"
        if "spreadsheet" in mime or "excel" in mime:
            return "Spreadsheet"
        if "word" in mime or "document" in mime:
            return "Document"
        if "presentation" in mime or "powerpoint" in mime:
            return "Presentation"
        return "Other"

    def _get_content_sync(self, file_id: str, mime_type: str) -> str:
        drive, docs = self._build_services()

        if mime_type == "application/vnd.google-apps.document":
            # Use Docs API for richer text extraction
            try:
                doc = docs.documents().get(documentId=file_id).execute()
                return self._extract_doc_text(doc.get("body", {}).get("content", []))
            except Exception as e:
                print(f"[DriveConnector] docs.get error ({file_id}): {e}")

        # Fallback: export as plain text via Drive export API
        try:
            content = drive.files().export(
                fileId=file_id,
                mimeType="text/plain",
            ).execute()
            if isinstance(content, bytes):
                return content.decode("utf-8", errors="replace")
            return str(content)
        except Exception as e:
            print(f"[DriveConnector] export error ({file_id}): {e}")
            return ""

    def _extract_doc_text(self, content: list) -> str:
        """Recursively extract plain text from Google Docs API body content."""
        parts: list[str] = []
        for element in content:
            if "paragraph" in element:
                para_text = ""
                for elem in element["paragraph"].get("elements", []):
                    if "textRun" in elem:
                        para_text += elem["textRun"].get("content", "")
                parts.append(para_text)
            elif "table" in element:
                for row in element["table"].get("tableRows", []):
                    for cell in row.get("tableCells", []):
                        parts.append(self._extract_doc_text(cell.get("content", [])))
            elif "sectionBreak" in element:
                parts.append("\n")
        return "".join(parts).strip()
