"""
KAIROS OAuth Handler — Backend-as-redirect-target pattern.

Flow:
  1. GET /oauth/{service}/start    → returns {url, service} (requires auth)
  2. User visits url → authorizes → service redirects to our callback
  3. GET /oauth/{service}/callback → exchanges code, stores token, closes popup
  4. GET /oauth/status             → returns connection status per service (requires auth)
  5. POST /oauth/disconnect/{service} → removes token (requires auth)

Tokens are stored in the existing kairos.db SQLite file under the oauth_tokens table.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse

from api.auth import get_current_user, UserProfile
from config import config

router = APIRouter(prefix="/oauth", tags=["oauth"])


# ── SQLite token store (piggybacks on kairos.db) ──────────────────────────────

def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(config.SQLITE_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS oauth_tokens (
            user_uid     TEXT NOT NULL,
            service      TEXT NOT NULL,
            token_data   TEXT NOT NULL,
            connected_at TEXT NOT NULL,
            PRIMARY KEY (user_uid, service)
        )
    """)
    conn.commit()
    return conn


def _store_token(user_uid: str, service: str, token_data: dict):
    conn = _get_conn()
    try:
        conn.execute(
            """INSERT OR REPLACE INTO oauth_tokens (user_uid, service, token_data, connected_at)
               VALUES (?, ?, ?, ?)""",
            (user_uid, service, json.dumps(token_data), datetime.utcnow().isoformat()),
        )
        conn.commit()
    finally:
        conn.close()


def _get_token(user_uid: str, service: str) -> dict | None:
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM oauth_tokens WHERE user_uid = ? AND service = ?",
            (user_uid, service),
        ).fetchone()
        if not row:
            return None
        data = json.loads(row["token_data"])
        data["connected_at"] = row["connected_at"]
        return data
    finally:
        conn.close()


def _delete_token(user_uid: str, service: str):
    conn = _get_conn()
    try:
        conn.execute(
            "DELETE FROM oauth_tokens WHERE user_uid = ? AND service = ?",
            (user_uid, service),
        )
        conn.commit()
    finally:
        conn.close()


# ── Popup HTML helpers ────────────────────────────────────────────────────────

_POPUP_STYLE = """
  body {
    background: #0b0b0c; color: #e4e4e7; font-family: monospace;
    display: flex; align-items: center; justify-content: center;
    height: 100vh; margin: 0;
  }
  .card {
    background: #1e1e20; border: 1px solid #27272a;
    padding: 28px 40px; border-radius: 12px; text-align: center;
    max-width: 320px;
  }
  .dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; margin-bottom: 12px; }
  .green { background: #22c55e; }
  .red   { background: #ef4444; }
  small  { color: #71717a; display: block; margin-top: 6px; }
"""


def _popup_success(service: str, detail: str) -> HTMLResponse:
    html = f"""<!DOCTYPE html><html><head><title>KAIROS</title>
<style>{_POPUP_STYLE}</style></head><body>
<div class="card">
  <div class="dot green"></div>
  <strong>{service.upper()} CONNECTED</strong>
  <small>{detail}</small>
  <small style="color:#52525b;margin-top:10px;">Closing window…</small>
</div>
<script>setTimeout(() => window.close(), 1500);</script>
</body></html>"""
    return HTMLResponse(content=html)


def _popup_error(msg: str) -> HTMLResponse:
    html = f"""<!DOCTYPE html><html><head><title>KAIROS</title>
<style>{_POPUP_STYLE}</style></head><body>
<div class="card" style="border-color:#7f1d1d;">
  <div class="dot red"></div>
  <strong style="color:#ef4444;">Connection Failed</strong>
  <small>{msg}</small>
  <small style="color:#52525b;margin-top:10px;">Closing window…</small>
</div>
<script>setTimeout(() => window.close(), 3000);</script>
</body></html>"""
    return HTMLResponse(content=html, status_code=400)


def _callback_url(service: str) -> str:
    """Redirect URI registered in each OAuth app — points to this backend."""
    return f"{config.BACKEND_URL}/api/oauth/{service}/callback"


# ── SLACK ─────────────────────────────────────────────────────────────────────

@router.get("/slack/start")
async def slack_start(current_user: UserProfile = Depends(get_current_user)):
    if not config.SLACK_CLIENT_ID or config.SLACK_CLIENT_ID == "your_client_id":
        sim_url = f"{_callback_url('slack')}?code=sim-slack-code&state={current_user.uid}"
        return {"service": "slack", "url": sim_url}

    scopes = "channels:history,channels:read,users:read,groups:history,groups:read"
    url = (
        "https://slack.com/oauth/v2/authorize"
        f"?client_id={config.SLACK_CLIENT_ID}"
        f"&scope={scopes}"
        f"&redirect_uri={_callback_url('slack')}"
        f"&state={current_user.uid}"
    )
    return {"service": "slack", "url": url}


@router.get("/slack/callback")
async def slack_callback(code: str = None, state: str = None, error: str = None):
    if error or not code or not state:
        return _popup_error(error or "Missing authorization code")

    if code == "sim-slack-code":
        team_name = "Helios Tech (Simulated)"
        _store_token(state, "slack", {
            "bot_token": "sim-slack-token-12345",
            "team_id": "T-SIMULATED",
            "team_name": team_name,
            "service": "slack",
        })
        print(f"[OAuth] ✅ Simulated Slack connected uid={state} team={team_name}")
        return _popup_success("Slack", f"Connected to {team_name} (Simulation)")

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://slack.com/api/oauth.v2.access",
                data={
                    "client_id": config.SLACK_CLIENT_ID,
                    "client_secret": config.SLACK_CLIENT_SECRET,
                    "code": code,
                    "redirect_uri": _callback_url("slack"),
                },
            )
        data = resp.json()
        if not data.get("ok"):
            return _popup_error(data.get("error", "Slack auth failed"))

        team_name = data.get("team_name") or data.get("team", {}).get("name", "Your Workspace")
        _store_token(state, "slack", {
            "bot_token": data.get("access_token"),
            "team_id": data.get("team_id"),
            "team_name": team_name,
            "service": "slack",
        })
        print(f"[OAuth] ✅ Slack connected uid={state} team={team_name}")
        return _popup_success("Slack", f"Connected to {team_name}")

    except Exception as e:
        print(f"[OAuth] 🔴 Slack callback error: {e}")
        return _popup_error(str(e))


# ── GMAIL + GOOGLE DRIVE (same Google OAuth flow) ─────────────────────────────

@router.get("/gmail/start")
async def gmail_start(current_user: UserProfile = Depends(get_current_user)):
    if not config.GOOGLE_CLIENT_ID or config.GOOGLE_CLIENT_ID == "your_client_id":
        sim_url = f"{_callback_url('gmail')}?code=sim-gmail-code&state={current_user.uid}"
        return {"service": "gmail", "url": sim_url}

    scopes = " ".join([
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/drive.readonly",
        "https://www.googleapis.com/auth/userinfo.email",
    ])
    from urllib.parse import quote
    url = (
        "https://accounts.google.com/o/oauth2/v2/auth"
        f"?client_id={config.GOOGLE_CLIENT_ID}"
        f"&scope={quote(scopes)}"
        f"&redirect_uri={_callback_url('gmail')}"
        "&response_type=code"
        f"&state={current_user.uid}"
        "&prompt=consent"
        "&access_type=offline"
    )
    return {"service": "gmail", "url": url}


@router.get("/gmail/callback")
async def gmail_callback(code: str = None, state: str = None, error: str = None):
    if error or not code or not state:
        return _popup_error(error or "Missing authorization code")

    if code == "sim-gmail-code":
        email = "developer@heliostech.com"
        _store_token(state, "google", {
            "refresh_token": "sim-google-refresh-token",
            "access_token": "sim-google-access-token",
            "email": email,
            "service": "google",
        })
        print(f"[OAuth] ✅ Simulated Gmail + Drive connected uid={state} email={email}")
        return _popup_success("Google", f"Gmail & Drive connected as {email} (Simulation)")

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "client_id": config.GOOGLE_CLIENT_ID,
                    "client_secret": config.GOOGLE_CLIENT_SECRET,
                    "code": code,
                    "redirect_uri": _callback_url("gmail"),
                    "grant_type": "authorization_code",
                },
            )
            data = resp.json()
            if "error" in data:
                return _popup_error(data["error"])

            # Fetch email address for display
            email = "your account"
            try:
                user_resp = await client.get(
                    "https://www.googleapis.com/oauth2/v1/userinfo",
                    headers={"Authorization": f"Bearer {data.get('access_token')}"},
                )
                email = user_resp.json().get("email", email)
            except Exception:
                pass

        _store_token(state, "google", {
            "refresh_token": data.get("refresh_token"),
            "access_token": data.get("access_token"),
            "email": email,
            "service": "google",
        })
        print(f"[OAuth] ✅ Gmail + Drive connected uid={state} email={email}")
        return _popup_success("Google", f"Gmail & Drive connected as {email}")

    except Exception as e:
        print(f"[OAuth] 🔴 Gmail callback error: {e}")
        return _popup_error(str(e))


# ── JIRA ──────────────────────────────────────────────────────────────────────

@router.get("/jira/start")
async def jira_start(current_user: UserProfile = Depends(get_current_user)):
    if not config.JIRA_CLIENT_ID or config.JIRA_CLIENT_ID == "your_client_id":
        sim_url = f"{_callback_url('jira')}?code=sim-jira-code&state={current_user.uid}"
        return {"service": "jira", "url": sim_url}

    url = (
        "https://auth.atlassian.com/authorize"
        f"?client_id={config.JIRA_CLIENT_ID}"
        "&response_type=code"
        f"&redirect_uri={_callback_url('jira')}"
        "&scope=read%3Ajira-work%20offline_access"
        f"&state={current_user.uid}"
        "&prompt=consent"
    )
    return {"service": "jira", "url": url}


@router.get("/jira/callback")
async def jira_callback(code: str = None, state: str = None, error: str = None):
    if error or not code or not state:
        return _popup_error(error or "Missing authorization code")

    if code == "sim-jira-code":
        email = "developer@heliostech.com"
        _store_token(state, "jira", {
            "access_token": "sim-jira-access-token",
            "refresh_token": "sim-jira-refresh-token",
            "email": email,
            "service": "jira",
        })
        print(f"[OAuth] ✅ Simulated Jira connected uid={state} email={email}")
        return _popup_success("Jira", f"Connected as {email} (Simulation)")

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://auth.atlassian.com/oauth/token",
                json={
                    "grant_type": "authorization_code",
                    "client_id": config.JIRA_CLIENT_ID,
                    "client_secret": config.JIRA_CLIENT_SECRET,
                    "code": code,
                    "redirect_uri": _callback_url("jira"),
                },
            )
            data = resp.json()
            if "error" in data:
                return _popup_error(data["error"])

            email = "your account"
            try:
                user_resp = await client.get(
                    "https://api.atlassian.com/me",
                    headers={"Authorization": f"Bearer {data.get('access_token')}"},
                )
                email = user_resp.json().get("email", email)
            except Exception:
                pass

        _store_token(state, "jira", {
            "access_token": data.get("access_token"),
            "refresh_token": data.get("refresh_token"),
            "email": email,
            "service": "jira",
        })
        print(f"[OAuth] ✅ Jira connected uid={state} email={email}")
        return _popup_success("Jira", f"Connected as {email}")

    except Exception as e:
        print(f"[OAuth] 🔴 Jira callback error: {e}")
        return _popup_error(str(e))


# ── ZOOM ──────────────────────────────────────────────────────────────────────

@router.get("/zoom/start")
async def zoom_start(current_user: UserProfile = Depends(get_current_user)):
    if not config.ZOOM_CLIENT_ID or config.ZOOM_CLIENT_ID == "your_client_id":
        sim_url = f"{_callback_url('zoom')}?code=sim-zoom-code&state={current_user.uid}"
        return {"service": "zoom", "url": sim_url}

    url = (
        "https://zoom.us/oauth/authorize"
        "?response_type=code"
        f"&client_id={config.ZOOM_CLIENT_ID}"
        f"&redirect_uri={_callback_url('zoom')}"
        f"&state={current_user.uid}"
    )
    return {"service": "zoom", "url": url}


@router.get("/zoom/callback")
async def zoom_callback(code: str = None, state: str = None, error: str = None):
    if error or not code or not state:
        return _popup_error(error or "Missing authorization code")

    if code == "sim-zoom-code":
        _store_token(state, "zoom", {
            "access_token": "sim-zoom-access-token",
            "refresh_token": "sim-zoom-refresh-token",
            "service": "zoom",
        })
        print(f"[OAuth] ✅ Simulated Zoom connected uid={state}")
        return _popup_success("Zoom", "Meeting transcription enabled (Simulation)")

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://zoom.us/oauth/token",
                params={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": _callback_url("zoom"),
                },
                auth=(config.ZOOM_CLIENT_ID, config.ZOOM_CLIENT_SECRET),
            )
        data = resp.json()
        if "error" in data:
            return _popup_error(data["error"])

        _store_token(state, "zoom", {
            "access_token": data.get("access_token"),
            "refresh_token": data.get("refresh_token"),
            "service": "zoom",
        })
        print(f"[OAuth] ✅ Zoom connected uid={state}")
        return _popup_success("Zoom", "Meeting transcription enabled")

    except Exception as e:
        print(f"[OAuth] 🔴 Zoom callback error: {e}")
        return _popup_error(str(e))


# ── STATUS + DISCONNECT ───────────────────────────────────────────────────────

@router.get("/status")
async def get_status(current_user: UserProfile = Depends(get_current_user)):
    """Returns connection status for all 4 OAuth services for the current user."""
    # frontend uses "gmail"; token is stored under "google" (Google OAuth covers Gmail+Drive)
    frontend_to_storage = {"slack": "slack", "gmail": "google", "jira": "jira", "zoom": "zoom"}
    result = {}
    for frontend_key, storage_key in frontend_to_storage.items():
        data = _get_token(current_user.uid, storage_key)
        if data:
            result[frontend_key] = {
                "connected": True,
                "connected_at": data.get("connected_at"),
                "service_name": data.get("team_name") or data.get("email") or frontend_key.title(),
            }
        else:
            result[frontend_key] = {"connected": False}
    return result


@router.post("/disconnect/{service}")
async def disconnect_service(
    service: str,
    current_user: UserProfile = Depends(get_current_user),
):
    valid = {"slack", "gmail", "jira", "zoom"}
    if service not in valid:
        raise HTTPException(400, f"Unknown service: {service}")
    # "gmail" in frontend maps to "google" in token store
    storage_key = "google" if service == "gmail" else service
    _delete_token(current_user.uid, storage_key)
    print(f"[OAuth] 🔓 {service} disconnected uid={current_user.uid}")
    return {"status": "disconnected", "service": service}
