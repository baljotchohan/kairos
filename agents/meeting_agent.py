"""
Meeting Agent — downloads Zoom recordings, transcribes with Whisper, feeds to synthesis.
"""

from __future__ import annotations

from config import config


class MeetingAgent:
    def _get_zoom_tokens(self, user_id: str | None = None) -> list[dict]:
        tokens = []
        try:
            import sqlite3
            conn = sqlite3.connect(config.SQLITE_PATH)
            conn.row_factory = sqlite3.Row
            if user_id:
                rows = conn.execute(
                    "SELECT token_data FROM oauth_tokens WHERE service = 'zoom' AND user_uid = ?",
                    (user_id,)
                ).fetchall()
            else:
                rows = conn.execute("SELECT token_data FROM oauth_tokens WHERE service = 'zoom'").fetchall()

            for r in rows:
                try:
                    from core.token_crypto import decrypt_token_data
                    data = decrypt_token_data(r["token_data"])
                except Exception:
                    continue
                if not data.get("disconnected") and data.get("mode") != "sim":
                    tokens.append(data)
            conn.close()
        except Exception as e:
            print(f"[MeetingAgent] Database error while reading Zoom tokens: {e}")

        # Fallback to server-side env if no user_id is requested or no tokens found
        if not tokens and not user_id and config.ZOOM_CLIENT_ID:
            tokens = [{
                "access_token": None,
                "refresh_token": None,
                "client_id": config.ZOOM_CLIENT_ID,
                "client_secret": config.ZOOM_CLIENT_SECRET,
            }]
        return tokens

    async def fetch(self, user_id: str | None = None) -> list[dict]:
        tokens = self._get_zoom_tokens(user_id=user_id)
        if not tokens:
            print(f"[MeetingAgent] No Zoom tokens configured for user {user_id} — skipping")
            return []

        from connectors.zoom_connector import ZoomConnector
        days_back = getattr(config, "EMAIL_LOOKBACK_DAYS", 30) or 30
        results = []

        for t in tokens:
            connector = ZoomConnector(
                access_token=t.get("access_token"),
                refresh_token=t.get("refresh_token"),
                client_id=t.get("client_id") or config.ZOOM_CLIENT_ID,
                client_secret=t.get("client_secret") or config.ZOOM_CLIENT_SECRET,
            )
            try:
                recordings = await connector.get_recordings(days_back=days_back)
            except Exception as e:
                print(f"[MeetingAgent] get_recordings failed: {e}")
                continue

            for rec in recordings:
                transcript = await self._transcribe(connector, rec)
                if transcript:
                    results.append({
                        "id": rec.get("uuid", rec.get("id", "")),
                        "title": rec.get("topic", "Zoom Meeting"),
                        "content": transcript,
                        "url": rec.get("share_url", ""),
                        "date": (rec.get("start_time", "") or "")[:10],
                        "participants": rec.get("participants", []),
                        "source": "Zoom",
                    })
        return results

    async def _transcribe(self, connector, rec: dict) -> str:
        """Download audio and transcribe — returns empty string if Whisper not available."""
        try:
            import whisper  # type: ignore[import-untyped]  # optional dep
        except ImportError:
            return ""

        download_url = rec.get("download_url", "")
        if not download_url:
            return ""

        try:
            audio_bytes = await connector.download_audio(download_url)
            if not audio_bytes:
                print("[MeetingAgent] Audio bytes download was empty — skipping transcription")
                return ""

            import tempfile, os
            import asyncio
            with tempfile.NamedTemporaryFile(suffix=".m4a", delete=False) as f:
                f.write(audio_bytes)
                tmp_path = f.name

            def run_whisper(path: str) -> str:
                model = whisper.load_model("base")
                result = model.transcribe(path)
                return result.get("text", "")

            text = await asyncio.to_thread(run_whisper, tmp_path)
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
            return text
        except Exception as e:
            print(f"[MeetingAgent] transcription failed: {e}")
        return ""
