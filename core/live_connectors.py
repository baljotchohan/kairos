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

import sqlite3
from typing import Optional

from config import config
from core.token_crypto import decrypt_token_data


def _read_token_rows(user_id: str, service: str, include_disconnected: bool = False) -> list[dict]:
    """Return token_data dicts for (user_id, service). Filters out rows marked
    disconnected unless include_disconnected=True — save_refreshed_token needs
    the raw (possibly-disconnected) row so it can tell a genuine disconnect
    apart from "no row yet" (see its docstring)."""
    out: list[dict] = []
    if not user_id:
        return out
    try:
        conn = sqlite3.connect(config.SQLITE_PATH, timeout=30.0)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=30000;")
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT token_data FROM oauth_tokens WHERE service = ? AND user_uid = ?",
            (service, user_id),
        ).fetchall()
        conn.close()
        for r in rows:
            try:
                data = decrypt_token_data(r["token_data"])
            except Exception:
                continue
            if include_disconnected or not data.get("disconnected"):
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


def save_refreshed_token(user_id: str, service: str, token_data: dict):
    """Save rotated OAuth token_data back to SQLite (encrypting it).

    Connectors call this with only the fields that actually changed on
    refresh (access_token, refresh_token, client_id/secret — see
    gmail_connector.py / drive_connector.py / zoom_connector.py). token_data
    is stored as a single encrypted JSON blob per (user_id, service), so a
    naive overwrite here would drop every OTHER field in that blob (e.g.
    `email`, set once at the original OAuth callback) the first time a token
    refreshes — merge onto the existing stored row instead.

    Reads the RAW row (including disconnected ones): a connector instance built
    before the user hit "Disconnect" can still be mid-flight and fire this
    callback afterward. If we merged onto the filtered (non-disconnected) view,
    `existing` would come back empty post-disconnect and this call would write
    a fresh, non-disconnected row — silently reviving a connection the user
    just severed. Detect that case and no-op instead.
    """
    from api.routes.oauth import _store_token
    existing = _read_token_rows(user_id, service, include_disconnected=True)
    if existing and existing[0].get("disconnected"):
        print(f"[LiveConnectors] Ignoring stale token refresh for disconnected {service}/{user_id}")
        return
    merged = {**existing[0], **token_data} if existing else token_data
    _store_token(user_id, service, merged)


def get_jira_oauth(user_id: str) -> Optional[dict]:
    """Return this user's real per-user Jira OAuth token_data, if any usable
    one is stored (needs cloud_id — a row without it can't be used for OAuth
    mode; see jira_connector.py's two auth modes)."""
    for data in _read_token_rows(user_id, "jira"):
        if data.get("cloud_id") and (data.get("access_token") or data.get("refresh_token")):
            return data
    return None


def get_notion_token(user_id: str) -> Optional[str]:
    """Return the Notion access_token (OAuth) or api_key (legacy) for this user."""
    for data in _read_token_rows(user_id, "notion"):
        token = data.get("access_token") or data.get("api_key")
        if token:
            return token
    return None


def get_github_token(user_id: str) -> Optional[str]:
    for data in _read_token_rows(user_id, "github"):
        token = data.get("access_token")
        if token:
            return token
    return None


def get_github_oauth(user_id: str) -> Optional[dict]:
    """Full GitHub token_data (access_token + optional refresh_token/expires_at),
    for callers that need to refresh — see get_github_token for a plain-token
    convenience wrapper used where refresh doesn't apply (e.g. Jira-style checks)."""
    for data in _read_token_rows(user_id, "github"):
        if data.get("access_token"):
            return data
    return None


def build_connectors_for_user(user_id: str) -> dict:
    """
    Build connector instances for every source the user has connected.

    Returns a dict with keys drive/gmail/slack/jira/zoom/notion (each a
    connector instance or None) plus "connected": the list of source names.
    """
    from connectors.drive_connector import DriveConnector
    from connectors.gmail_connector import GmailConnector
    from connectors.slack_connector import SlackConnector
    from connectors.jira_connector import JiraConnector
    from connectors.zoom_connector import ZoomConnector
    from connectors.notion_connector import NotionConnector
    from connectors.github_connector import GitHubConnector

    out: dict = {
        "drive": None, "gmail": None, "slack": None,
        "jira": None, "zoom": None, "notion": None, "github": None, "connected": [],
    }

    google = get_google_token(user_id)
    if google and google.get("refresh_token"):
        google_refresh_cb = lambda data: save_refreshed_token(user_id, "google", data)
        out["drive"] = DriveConnector(
            access_token=google.get("access_token"),
            refresh_token=google.get("refresh_token"),
            client_id=google.get("client_id"),
            client_secret=google.get("client_secret"),
            on_token_refresh=google_refresh_cb,
        )
        out["gmail"] = GmailConnector(
            access_token=google.get("access_token"),
            refresh_token=google.get("refresh_token"),
            client_id=google.get("client_id"),
            client_secret=google.get("client_secret"),
            on_token_refresh=google_refresh_cb,
        )
        out["connected"] += ["drive", "gmail"]

    slack_token = get_slack_token(user_id)
    if slack_token:
        out["slack"] = SlackConnector(token=slack_token)
        out["connected"].append("slack")

    zoom = get_zoom_token(user_id)
    if zoom:
        zoom_refresh_cb = lambda data: save_refreshed_token(user_id, "zoom", data)
        out["zoom"] = ZoomConnector(
            access_token=zoom.get("access_token"),
            refresh_token=zoom.get("refresh_token"),
            client_id=zoom.get("client_id") or config.ZOOM_CLIENT_ID,
            client_secret=zoom.get("client_secret") or config.ZOOM_CLIENT_SECRET,
            expires_at=zoom.get("expires_at"),
            allow_s2s=False,  # Enforce strict user isolation — disable global credential fallback
            on_token_refresh=zoom_refresh_cb,
        )
        out["connected"].append("zoom")

    # Jira: prefer a real per-user OAuth token when this user has connected
    # their own Jira (Bearer auth against their own accessible site — see
    # jira_connector.py's OAuth mode). Only fall back to the global
    # single-tenant admin credential for the configured owner uid, and only
    # when they haven't done real per-user OAuth — otherwise every user
    # (incl. anonymous guests) would be served the deployer's private Jira.
    jira_oauth = get_jira_oauth(user_id)
    if jira_oauth:
        jira_refresh_cb = lambda data: save_refreshed_token(user_id, "jira", data)
        out["jira"] = JiraConnector(
            access_token=jira_oauth.get("access_token"),
            refresh_token=jira_oauth.get("refresh_token"),
            cloud_id=jira_oauth.get("cloud_id"),
            expires_at=jira_oauth.get("expires_at"),
            on_token_refresh=jira_refresh_cb,
        )
        out["connected"].append("jira")
    elif (
        user_id and user_id == config.JIRA_OWNER_UID
        and config.JIRA_URL and config.JIRA_EMAIL and config.JIRA_API_TOKEN
    ):
        out["jira"] = JiraConnector()
        out["connected"].append("jira")

    notion_token = get_notion_token(user_id)
    if notion_token:
        out["notion"] = NotionConnector(api_key=notion_token)
        out["connected"].append("notion")

    github_oauth = get_github_oauth(user_id)
    if github_oauth:
        out["github"] = GitHubConnector(
            access_token=github_oauth.get("access_token"),
            refresh_token=github_oauth.get("refresh_token"),
            expires_at=github_oauth.get("expires_at"),
            on_token_refresh=lambda data: save_refreshed_token(user_id, "github", data),
        )
        out["connected"].append("github")

    return out
