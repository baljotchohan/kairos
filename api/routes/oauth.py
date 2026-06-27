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
import hmac
import hashlib
import time
import os
from datetime import datetime

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse

from api.auth import get_current_user, UserProfile
from config import config

router = APIRouter(prefix="/oauth", tags=["oauth"])

# Ephemeral key generated at startup for signing OAuth state parameters
_OAUTH_SIGNING_KEY = os.urandom(32)

def _generate_state_token(uid: str) -> str:
    """Generates a signed state token containing the user UID and an expiry timestamp."""
    expires = int(time.time()) + 600  # 10 minutes expiry
    payload = f"{uid}:{expires}"
    sig = hmac.new(_OAUTH_SIGNING_KEY, payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}:{sig}"

def _verify_state_token(state: str) -> str | None:
    """Verifies the signed state token and returns user UID if valid."""
    try:
        parts = state.split(":")
        if len(parts) != 3:
            return None
        uid, expires_str, sig = parts
        expires = int(expires_str)
        if time.time() > expires:
            return None  # Token expired
        payload = f"{uid}:{expires_str}"
        expected_sig = hmac.new(_OAUTH_SIGNING_KEY, payload.encode(), hashlib.sha256).hexdigest()
        if hmac.compare_digest(sig, expected_sig):
            return uid
    except Exception:
        pass
    return None

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
    state = _generate_state_token(current_user.uid)
    if not config.SLACK_CLIENT_ID or config.SLACK_CLIENT_ID == "your_client_id":
        sim_url = f"{_callback_url('slack')}?code=sim-slack-code&state={state}"
        return {"service": "slack", "url": sim_url}

    scopes = "channels:history,channels:read,users:read,groups:history,groups:read"
    url = (
        "https://slack.com/oauth/v2/authorize"
        f"?client_id={config.SLACK_CLIENT_ID}"
        f"&scope={scopes}"
        f"&redirect_uri={_callback_url('slack')}"
        f"&state={state}"
    )
    return {"service": "slack", "url": url}


@router.get("/slack/callback")
async def slack_callback(code: str = None, state: str = None, error: str = None):
    if error or not code or not state:
        return _popup_error(error or "Missing authorization code")

    verified_uid = _verify_state_token(state)
    if not verified_uid:
        return _popup_error("Security Check Failed: Invalid or expired OAuth state parameter.")

    if code == "sim-slack-code":
        team_name = "Helios Tech (Simulated)"
        _store_token(verified_uid, "slack", {
            "bot_token": "sim-slack-token-12345",
            "team_id": "T-SIMULATED",
            "team_name": team_name,
            "service": "slack",
        })
        print(f"[OAuth] ✅ Simulated Slack connected uid={verified_uid} team={team_name}")
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
        _store_token(verified_uid, "slack", {
            "bot_token": data.get("access_token"),
            "team_id": data.get("team_id"),
            "team_name": team_name,
            "service": "slack",
        })
        print(f"[OAuth] ✅ Slack connected uid={verified_uid} team={team_name}")
        return _popup_success("Slack", f"Connected to {team_name}")

    except Exception as e:
        print(f"[OAuth] 🔴 Slack callback error: {e}")
        return _popup_error("We couldn't complete the connection. Please try again.")


# ── GMAIL + GOOGLE DRIVE (same Google OAuth flow) ─────────────────────────────

@router.get("/gmail/start")
async def gmail_start(current_user: UserProfile = Depends(get_current_user)):
    state = _generate_state_token(current_user.uid)
    if not config.GOOGLE_CLIENT_ID or config.GOOGLE_CLIENT_ID == "your_client_id":
        sim_url = f"{_callback_url('gmail')}?code=sim-gmail-code&state={state}"
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
        f"&state={state}"
        "&prompt=consent"
        "&access_type=offline"
    )
    return {"service": "gmail", "url": url}


@router.get("/gmail/callback")
async def gmail_callback(code: str = None, state: str = None, error: str = None):
    if error or not code or not state:
        return _popup_error(error or "Missing authorization code")

    verified_uid = _verify_state_token(state)
    if not verified_uid:
        return _popup_error("Security Check Failed: Invalid or expired OAuth state parameter.")

    if code == "sim-gmail-code":
        email = "developer@heliostech.com"
        _store_token(verified_uid, "google", {
            "refresh_token": "sim-google-refresh-token",
            "access_token": "sim-google-access-token",
            "email": email,
            "service": "google",
        })
        print(f"[OAuth] ✅ Simulated Gmail + Drive connected uid={verified_uid} email={email}")
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

        _store_token(verified_uid, "google", {
            "refresh_token": data.get("refresh_token"),
            "access_token": data.get("access_token"),
            "email": email,
            "service": "google",
        })
        print(f"[OAuth] ✅ Gmail + Drive connected uid={verified_uid} email={email}")
        return _popup_success("Google", f"Gmail & Drive connected as {email}")

    except Exception as e:
        print(f"[OAuth] 🔴 Gmail callback error: {e}")
        return _popup_error("We couldn't complete the connection. Please try again.")


@router.get("/drive/start")
async def drive_start(current_user: UserProfile = Depends(get_current_user)):
    """Google Drive shares Google's single OAuth grant with Gmail (one consent
    covers both gmail.readonly + drive.readonly scopes). So the Drive card runs
    the exact same Google flow + callback as Gmail and stores the same `google`
    token — connecting either card lights up both. This avoids registering a
    second redirect URI in Google Cloud Console."""
    res = await gmail_start(current_user)
    res["service"] = "drive"
    return res


# ── JIRA ──────────────────────────────────────────────────────────────────────

@router.get("/jira/start")
async def jira_start(current_user: UserProfile = Depends(get_current_user)):
    state = _generate_state_token(current_user.uid)
    # Real OAuth if client credentials are configured
    if not config.JIRA_CLIENT_ID or config.JIRA_CLIENT_ID == "your_client_id":
        sim_url = f"{_callback_url('jira')}?code=sim-jira-code&state={state}"
        return {"service": "jira", "url": sim_url}

    url = (
        "https://auth.atlassian.com/authorize"
        f"?client_id={config.JIRA_CLIENT_ID}"
        "&response_type=code"
        f"&redirect_uri={_callback_url('jira')}"
        "&scope=read%3Ajira-work%20offline_access"
        f"&state={state}"
        "&prompt=consent"
    )
    return {"service": "jira", "url": url}


@router.get("/jira/callback")
async def jira_callback(code: str = None, state: str = None, error: str = None):
    if error or not code or not state:
        return _popup_error(error or "Missing authorization code")

    verified_uid = _verify_state_token(state)
    if not verified_uid:
        return _popup_error("Security Check Failed: Invalid or expired OAuth state parameter.")

    if code == "sim-jira-code":
        workspace = config.JIRA_URL.replace("https://", "") if config.JIRA_URL else "Jira"
        _store_token(verified_uid, "jira", {
            "access_token": config.JIRA_API_TOKEN,
            "email": config.JIRA_EMAIL,
            "workspace": workspace,
            "service": "jira",
        })
        print(f"[OAuth] ✅ Jira connected uid={verified_uid} workspace={workspace}")
        return _popup_success("Jira", f"Connected to {workspace}")

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

        _store_token(verified_uid, "jira", {
            "access_token": data.get("access_token"),
            "refresh_token": data.get("refresh_token"),
            "email": email,
            "service": "jira",
        })
        print(f"[OAuth] ✅ Jira connected uid={verified_uid} email={email}")
        return _popup_success("Jira", f"Connected as {email}")

    except Exception as e:
        print(f"[OAuth] 🔴 Jira callback error: {e}")
        return _popup_error("We couldn't complete the connection. Please try again.")


# ── ZOOM ──────────────────────────────────────────────────────────────────────

@router.get("/zoom/start")
async def zoom_start(current_user: UserProfile = Depends(get_current_user)):
    state = _generate_state_token(current_user.uid)

    # Server-to-Server app (account_credentials grant): there is NO user consent
    # screen for this grant type, so opening a popup would just flash our own
    # callback. Connect server-side immediately and tell the frontend it's done
    # (no `url` → the button skips the popup and refreshes to "Connected").
    if config.ZOOM_ACCOUNT_ID and config.ZOOM_CLIENT_ID and config.ZOOM_CLIENT_SECRET:
        _store_token(current_user.uid, "zoom", {
            "mode": "s2s",
            "account_id": config.ZOOM_ACCOUNT_ID,
            "client_id": config.ZOOM_CLIENT_ID,
            "client_secret": config.ZOOM_CLIENT_SECRET,
            "service": "zoom",
        })
        print(f"[OAuth] ✅ Zoom (S2S) connected uid={current_user.uid}")
        return {"service": "zoom", "connected": True,
                "message": "Zoom connected via account credentials."}

    # No real credentials configured → simulated connect (demo mode).
    if not config.ZOOM_CLIENT_ID or config.ZOOM_CLIENT_ID == "your_client_id":
        sim_url = f"{_callback_url('zoom')}?code=sim-zoom-code&state={state}"
        return {"service": "zoom", "url": sim_url}

    # User-managed OAuth app → real Zoom consent popup (redirect_uri URL-encoded).
    from urllib.parse import quote
    url = (
        "https://zoom.us/oauth/authorize"
        "?response_type=code"
        f"&client_id={config.ZOOM_CLIENT_ID}"
        f"&redirect_uri={quote(_callback_url('zoom'), safe='')}"
        f"&state={state}"
    )
    return {"service": "zoom", "url": url}


@router.get("/zoom/callback")
async def zoom_callback(code: str = None, state: str = None, error: str = None):
    if error or not code or not state:
        return _popup_error(error or "Missing authorization code")

    verified_uid = _verify_state_token(state)
    if not verified_uid:
        return _popup_error("Security Check Failed: Invalid or expired OAuth state parameter.")

    if code == "sim-zoom-code":
        _store_token(verified_uid, "zoom", {
            "mode": "sim",
            "service": "zoom",
        })
        print(f"[OAuth] ✅ Zoom connected (demo) uid={verified_uid}")
        return _popup_success("Zoom", "Meeting transcription enabled (demo)")

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

        _store_token(verified_uid, "zoom", {
            "access_token": data.get("access_token"),
            "refresh_token": data.get("refresh_token"),
            "service": "zoom",
        })
        print(f"[OAuth] ✅ Zoom connected uid={verified_uid}")
        return _popup_success("Zoom", "Meeting transcription enabled")

    except Exception as e:
        print(f"[OAuth] 🔴 Zoom callback error: {e}")
        return _popup_error("We couldn't complete the connection. Please try again.")


# ── STATUS + DISCONNECT ───────────────────────────────────────────────────────

@router.get("/status")
async def get_status(current_user: UserProfile = Depends(get_current_user)):
    """Returns connection status for all 4 OAuth services for the current user.
    Only shows connected when the user has explicitly connected via OAuth popup."""

    # Gmail + Drive both read the single Google grant (one consent covers both).
    frontend_to_storage = {
        "slack": "slack", "gmail": "google", "drive": "google",
        "jira": "jira", "zoom": "zoom",
    }

    result = {}
    for frontend_key, storage_key in frontend_to_storage.items():
        data = _get_token(current_user.uid, storage_key)
        if data and not data.get("disconnected"):
            result[frontend_key] = {
                "connected": True,
                "connected_at": data.get("connected_at"),
                "service_name": data.get("team_name") or data.get("email") or data.get("workspace") or frontend_key.title(),
            }
        else:
            result[frontend_key] = {"connected": False}
    return result


@router.post("/disconnect/{service}")
async def disconnect_service(
    service: str,
    current_user: UserProfile = Depends(get_current_user),
):
    valid = {"slack", "gmail", "drive", "jira", "zoom"}
    if service not in valid:
        raise HTTPException(400, f"Unknown service: {service}")
    # "gmail" and "drive" both map to the single "google" grant in the token store
    storage_key = "google" if service in ("gmail", "drive") else service
    # Mark as disconnected in DB to prevent re-inheriting env fallback
    _store_token(current_user.uid, storage_key, {"disconnected": True})
    print(f"[OAuth] 🔓 {service} disconnected uid={current_user.uid}")
    return {"status": "disconnected", "service": service}
