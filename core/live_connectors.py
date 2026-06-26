"""
Per-user live connector factory.

Builds ready-to-use connector instances from the OAuth tokens a user has stored
(the `oauth_tokens` table). Centralizes the token-reading that each ingestion
agent does individually, and powers the LiveDataAgent's on-demand queries
("what's in my Drive?", "show my last email", "how many files do I have?").

No env fallback: if a user hasn't connected a source, its connector is simply
absent — so the agent can honestly say the source isn't connected, and one
user's data can never be served from another user's (or the server's) tokens.
"""

from __future__ import annotations

import json
import sqlite3
from typing import Optional

from config import config


def _read_token_rows(user_id: str, service: str) -> list[dict]:
    """Return non-disconnected token_data dicts for (user_id, service)."""
    out: list[dict] = []
    if not user_id:
        return out
    try:
        conn = sqlite3.connect(config.SQLITE_PATH)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT token_data FROM oauth_tokens WHERE service = ? AND user_uid = ?",
            (service, user_id),
        ).fetchall()
        conn.close()
        for r in rows:
            try:
                data = json.loads(r["token_data"])
            except Exception:
                continue
            if not data.get("disconnected"):
                out.append(data)
    except Exception as e:
        print(f"[LiveConnectors] token read error ({service}/{user_id}): {e}")
    return out


def get_google_token(user_id: str) -> Optional[dict]:
    rows = _read_token_rows(user_id, "google")
    return rows[0] if rows else None


def get_slack_token(user_id: str) -> Optional[str]:
    for data in _read_token_rows(user_id, "slack"):
        if data.get("bot_token"):
            return data["bot_token"]
    return None


def get_zoom_token(user_id: str) -> Optional[dict]:
    rows = _read_token_rows(user_id, "zoom")
    return rows[0] if rows else None


def build_connectors_for_user(user_id: str) -> dict:
    """
    Build connector instances for every source the user has connected.

    Returns a dict with keys drive/gmail/slack/jira/zoom (each a connector
    instance or None) plus "connected": the list of available source names.
    """
    from connectors.drive_connector import DriveConnector
    from connectors.gmail_connector import GmailConnector
    from connectors.slack_connector import SlackConnector
    from connectors.jira_connector import JiraConnector
    from connectors.zoom_connector import ZoomConnector

    out: dict = {
        "drive": None, "gmail": None, "slack": None,
        "jira": None, "zoom": None, "connected": [],
    }

    google = get_google_token(user_id)
    if google and google.get("refresh_token"):
        out["drive"] = DriveConnector(
            refresh_token=google.get("refresh_token"),
            client_id=google.get("client_id"),
            client_secret=google.get("client_secret"),
        )
        out["gmail"] = GmailConnector(
            refresh_token=google.get("refresh_token"),
            client_id=google.get("client_id"),
            client_secret=google.get("client_secret"),
        )
        out["connected"] += ["drive", "gmail"]

    slack_token = get_slack_token(user_id)
    if slack_token:
        out["slack"] = SlackConnector(token=slack_token)
        out["connected"].append("slack")

    zoom = get_zoom_token(user_id)
    if zoom:
        out["zoom"] = ZoomConnector(
            access_token=zoom.get("access_token"),
            refresh_token=zoom.get("refresh_token"),
            client_id=zoom.get("client_id") or config.ZOOM_CLIENT_ID,
            client_secret=zoom.get("client_secret") or config.ZOOM_CLIENT_SECRET,
        )
        out["connected"].append("zoom")

    # Jira is currently configured globally (no per-user OAuth stored yet).
    if config.JIRA_URL and config.JIRA_EMAIL and config.JIRA_API_TOKEN:
        out["jira"] = JiraConnector()
        out["connected"].append("jira")

    return out
