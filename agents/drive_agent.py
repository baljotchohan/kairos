"""
Drive Agent — fetches Google Drive documents for synthesis.
"""

from __future__ import annotations

from config import config


class DriveAgent:
    def _get_google_tokens(self, user_id: str | None = None) -> list[dict]:
        tokens = []
        try:
            import sqlite3
            conn = sqlite3.connect(config.SQLITE_PATH)
            conn.row_factory = sqlite3.Row
            if user_id:
                rows = conn.execute(
                    "SELECT token_data FROM oauth_tokens WHERE service = 'google' AND user_uid = ?",
                    (user_id,)
                ).fetchall()
            else:
                rows = conn.execute("SELECT token_data FROM oauth_tokens WHERE service = 'google'").fetchall()

            for r in rows:
                try:
                    from core.token_crypto import decrypt_token_data
                    data = decrypt_token_data(r["token_data"])
                except Exception:
                    continue
                if not data.get("disconnected") and data.get("refresh_token") != "sim-google-refresh-token":
                    tokens.append(data)
            conn.close()
        except Exception as e:
            print(f"[DriveAgent] Database error while reading Google tokens: {e}")

        # Fallback to server-side env if no user_id is requested or no tokens found
        if not tokens and not user_id and config.GOOGLE_REFRESH_TOKEN:
            tokens = [{
                "refresh_token": config.GOOGLE_REFRESH_TOKEN,
                "client_id": config.GOOGLE_CLIENT_ID,
                "client_secret": config.GOOGLE_CLIENT_SECRET,
            }]
        return tokens

    async def fetch(self, user_id: str | None = None) -> list[dict]:
        tokens = self._get_google_tokens(user_id=user_id)
        if not tokens:
            print(f"[DriveAgent] No Google tokens configured for user {user_id} — skipping")
            return []

        from connectors.drive_connector import DriveConnector
        days_back = getattr(config, "EMAIL_LOOKBACK_DAYS", 30) or 30
        results = []

        for t in tokens:
            connector = DriveConnector(
                refresh_token=t.get("refresh_token"),
                client_id=t.get("client_id"),
                client_secret=t.get("client_secret"),
            )
            try:
                files = await connector.list_files(days_back=days_back)
            except Exception as e:
                print(f"[DriveAgent] list_files failed: {e}")
                continue

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
