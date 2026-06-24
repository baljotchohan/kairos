"""
Meeting Agent — downloads Zoom recordings, transcribes with Whisper, feeds to synthesis.
"""

from __future__ import annotations

from config import config


class MeetingAgent:
    async def fetch(self) -> list[dict]:
        if not config.ZOOM_CLIENT_ID:
            print("[MeetingAgent] No ZOOM_CLIENT_ID configured — skipping")
            return []

        from connectors.zoom_connector import ZoomConnector
        connector = ZoomConnector()
        days_back = getattr(config, "EMAIL_LOOKBACK_DAYS", 30) or 30

        try:
            recordings = await connector.get_recordings(days_back=days_back)
        except Exception as e:
            print(f"[MeetingAgent] get_recordings failed: {e}")
            return []

        results = []
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
            return rec.get("topic", "")

        download_url = rec.get("download_url", "")
        if not download_url:
            return ""

        try:
            audio_bytes = await connector.download_audio(download_url)
            import tempfile, os
            with tempfile.NamedTemporaryFile(suffix=".m4a", delete=False) as f:
                f.write(audio_bytes)
                tmp_path = f.name
            model = whisper.load_model("base")
            result = model.transcribe(tmp_path)
            os.unlink(tmp_path)
            return result.get("text", "")
        except Exception as e:
            print(f"[MeetingAgent] transcription failed: {e}")
        return ""
