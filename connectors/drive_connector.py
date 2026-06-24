"""
Google Drive connector — reads documents, meeting notes, proposals, specs.
Requires Google OAuth with drive.readonly + documents.readonly scopes.
Returns gracefully empty list when credentials are missing.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

from config import config


class DriveConnector:
    SCOPES = [
        "https://www.googleapis.com/auth/drive.readonly",
        "https://www.googleapis.com/auth/documents.readonly",
    ]

    def __init__(self):
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
            token=None,
            refresh_token=config.GOOGLE_REFRESH_TOKEN,
            client_id=config.GOOGLE_CLIENT_ID,
            client_secret=config.GOOGLE_CLIENT_SECRET,
            token_uri="https://oauth2.googleapis.com/token",
            scopes=self.SCOPES,
        )
        creds.refresh(Request())
        self._drive = build("drive", "v3", credentials=creds)
        self._docs = build("docs", "v1", credentials=creds)
        return self._drive, self._docs

    # ── Public async API ───────────────────────────────────────────────────────

    async def list_files(self, days_back: int) -> list[dict]:
        """
        List recently modified Google Docs.
        Returns list of dicts: {id, name, mimeType, modifiedTime, webViewLink}.
        """
        if not config.GOOGLE_REFRESH_TOKEN:
            return []

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._list_files_sync, days_back)

    async def get_file_content(self, file_id: str, mime_type: str) -> str:
        """
        Export a Drive file and return its plain-text content.
        Handles Google Docs natively; exports other types via Drive export API.
        """
        if not config.GOOGLE_REFRESH_TOKEN:
            return ""

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._get_content_sync, file_id, mime_type)

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
