"""
Drive Agent — fetches Google Drive documents for synthesis.
"""

from __future__ import annotations

from config import config


class DriveAgent:
    async def fetch(self) -> list[dict]:
        if not config.GOOGLE_REFRESH_TOKEN:
            print("[DriveAgent] No GOOGLE_REFRESH_TOKEN configured — skipping")
            return []

        from connectors.drive_connector import DriveConnector
        connector = DriveConnector()
        days_back = getattr(config, "EMAIL_LOOKBACK_DAYS", 30) or 30

        try:
            files = await connector.list_files(days_back=days_back)
        except Exception as e:
            print(f"[DriveAgent] list_files failed: {e}")
            return []

        results = []
        for f in files:
            try:
                content = await connector.get_file_content(f["id"], f.get("mimeType", ""))
                results.append({
                    "id": f["id"],
                    "title": f.get("name", ""),
                    "content": content,
                    "url": f.get("webViewLink", ""),
                    "date": (f.get("modifiedTime", "") or "")[:10],
                    "source": "Google Drive",
                })
            except Exception as e:
                print(f"[DriveAgent] get_file_content {f['id']} failed: {e}")

        return results
