"""
Zoom connector — lists cloud recordings and downloads audio for transcription.
Uses Zoom Server-to-Server OAuth (account_credentials grant type).
Transcription is handled by MeetingAgent via Fireworks Whisper endpoint.
Returns gracefully empty list when credentials are missing.
"""

from __future__ import annotations

import base64
from datetime import datetime, timedelta
from typing import Optional, Callable

import httpx

from config import config


class ZoomConnector:
    TOKEN_URL = "https://zoom.us/oauth/token"
    API_BASE = "https://api.zoom.us/v2"

    def __init__(
        self,
        access_token: str | None = None,
        refresh_token: str | None = None,
        client_id: str | None = None,
        client_secret: str | None = None,
        expires_at: int | None = None,
        allow_s2s: bool = True,
        on_token_refresh: Callable[[dict], None] | None = None,
    ):
        self._access_token = access_token
        self.refresh_token = refresh_token
        self.client_id = client_id or config.ZOOM_CLIENT_ID
        self.client_secret = client_secret or config.ZOOM_CLIENT_SECRET
        self.expires_at = expires_at
        self.allow_s2s = allow_s2s
        self.on_token_refresh = on_token_refresh

    # ── Auth ───────────────────────────────────────────────────────────────────

    async def _get_token(self) -> str:
        """Obtain a Server-to-Server OAuth2 access token or refresh user OAuth token."""
        import time
        if self._access_token and (self.expires_at is None or time.time() < self.expires_at - 60):
            return self._access_token

        if self.refresh_token:
            creds = base64.b64encode(
                f"{self.client_id}:{self.client_secret}".encode()
            ).decode()
            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.post(
                    self.TOKEN_URL,
                    headers={"Authorization": f"Basic {creds}"},
                    params={
                        "grant_type": "refresh_token",
                        "refresh_token": self.refresh_token,
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                self._access_token = data["access_token"]
                if "refresh_token" in data:
                    self.refresh_token = data["refresh_token"]
                
                # Calculate absolute expires_at if possible
                expires_in = data.get("expires_in", 3599)
                self.expires_at = int(time.time()) + expires_in
                
                if self.on_token_refresh:
                    # Save rotated token back to DB
                    self.on_token_refresh({
                        "access_token": self._access_token,
                        "refresh_token": self.refresh_token,
                        "expires_in": expires_in,
                        "expires_at": self.expires_at
                    })
                return self._access_token

        if not self.allow_s2s:
            raise RuntimeError("User Zoom connection expired and Server-to-Server fallback is disabled.")

        creds = base64.b64encode(
            f"{self.client_id}:{self.client_secret}".encode()
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
            data = resp.json()
            self._access_token = data["access_token"]
            expires_in = data.get("expires_in", 3599)
            self.expires_at = int(time.time()) + expires_in
            return self._access_token

    # ── Public async API ───────────────────────────────────────────────────────

    async def get_recordings(self, days_back: int) -> list[dict]:
        """
        List cloud recordings from the last `days_back` days.
        """
        if not self.refresh_token and (not config.ZOOM_ACCOUNT_ID or not self.client_id or not self.client_secret):
            return []

        token = await self._get_token()
        from_date = (datetime.utcnow() - timedelta(days=days_back)).strftime("%Y-%m-%d")
        to_date = datetime.utcnow().strftime("%Y-%m-%d")

        async with httpx.AsyncClient(timeout=30) as client:
            try:
                resp = await client.get(
                    f"{self.API_BASE}/users/me/recordings",
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
