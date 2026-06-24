"""
Zoom connector — lists cloud recordings and downloads audio for transcription.
Uses Zoom Server-to-Server OAuth (account_credentials grant type).
Transcription is handled by MeetingAgent via Fireworks Whisper endpoint.
Returns gracefully empty list when credentials are missing.
"""

from __future__ import annotations

import base64
from datetime import datetime, timedelta
from typing import Optional

import httpx

from config import config


class ZoomConnector:
    TOKEN_URL = "https://zoom.us/oauth/token"
    API_BASE = "https://api.zoom.us/v2"

    def __init__(self):
        self._access_token: Optional[str] = None

    # ── Auth ───────────────────────────────────────────────────────────────────

    async def _get_token(self) -> str:
        """Obtain a Server-to-Server OAuth2 access token."""
        if self._access_token:
            return self._access_token

        creds = base64.b64encode(
            f"{config.ZOOM_CLIENT_ID}:{config.ZOOM_CLIENT_SECRET}".encode()
        ).decode()

        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(
                self.TOKEN_URL,
                headers={"Authorization": f"Basic {creds}"},
                params={
                    "grant_type": "account_credentials",
                    "account_id": config.ZOOM_ACCOUNT_ID,
                },
            )
            resp.raise_for_status()
            self._access_token = resp.json()["access_token"]
            return self._access_token

    # ── Public async API ───────────────────────────────────────────────────────

    async def get_recordings(self, days_back: int) -> list[dict]:
        """
        List cloud recordings from the last `days_back` days.
        Returns list of dicts: {uuid, topic, start_time, host_email,
                                 download_url, duration}.
        """
        if not config.ZOOM_ACCOUNT_ID or not config.ZOOM_CLIENT_ID or not config.ZOOM_CLIENT_SECRET:
            return []

        token = await self._get_token()
        from_date = (datetime.utcnow() - timedelta(days=days_back)).strftime("%Y-%m-%d")
        to_date = datetime.utcnow().strftime("%Y-%m-%d")

        async with httpx.AsyncClient(timeout=30) as client:
            try:
                resp = await client.get(
                    f"{self.API_BASE}/accounts/me/recordings",
                    headers={"Authorization": f"Bearer {token}"},
                    params={"from": from_date, "to": to_date, "page_size": 100},
                )
                resp.raise_for_status()
                meetings = resp.json().get("meetings", [])
            except Exception as e:
                print(f"[ZoomConnector] get_recordings error: {e}")
                return []

        recordings: list[dict] = []
        for meeting in meetings:
            # Find the best audio/video file to download
            files = meeting.get("recording_files", [])
            audio_file = next(
                (f for f in files if f.get("file_type") in ("M4A", "MP4") and f.get("download_url")),
                None,
            )
            if not audio_file:
                continue

            recordings.append({
                "uuid": meeting.get("uuid", ""),
                "topic": meeting.get("topic", "Meeting"),
                "start_time": meeting.get("start_time", ""),
                "host_email": meeting.get("host_email", ""),
                "download_url": audio_file["download_url"],
                "share_url": meeting.get("share_url", ""),
                "duration": meeting.get("duration", 0),
                "file_type": audio_file["file_type"],
            })

        print(f"[ZoomConnector] Found {len(recordings)} recordings")
        return recordings

    async def download_audio(self, download_url: str) -> bytes:
        """
        Download audio bytes from a Zoom recording download URL.
        Appends the access token as a query param (Zoom requires this).
        """
        token = await self._get_token()
        url = f"{download_url}?access_token={token}"

        async with httpx.AsyncClient(timeout=300, follow_redirects=True) as client:
            try:
                resp = await client.get(url)
                resp.raise_for_status()
                return resp.content
            except Exception as e:
                print(f"[ZoomConnector] download_audio error: {e}")
                return b""
