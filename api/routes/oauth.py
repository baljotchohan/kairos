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

import sqlite3
import hmac
import hashlib
import html
import time
import os
import base64
from datetime import datetime
from urllib.parse import quote

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import HTMLResponse

from api.auth import get_current_user, UserProfile
from config import config
from core.token_crypto import encrypt_token_data, decrypt_token_data

router = APIRouter(prefix="/oauth", tags=["oauth"])


def _oauth_signing_key() -> bytes:
    """Persistent signing key for OAuth state tokens, derived from a stable
    environment secret. Every /oauth/{service}/callback is unauthenticated
    and trusts the state token alone to bind a connector token to a
    user_uid — if this key were guessable, an attacker could forge a state
    for an arbitrary victim uid and have their own connector credentials
    written into that victim's oauth_tokens row. So, like
    core/token_crypto.py's cipher key and core/mcp_auth.py's signing secret,
    refuse to fall back to a hardcoded value in production; only dev/test
    may use the deterministic fallback. Computed lazily (not at import time)
    so the production check runs per-call, matching mcp_auth.py's _secret()
    — at import time PYTEST_CURRENT_TEST isn't set yet, so an eager,
    module-level check would wrongly reject test collection too.
    """
    explicit = os.environ.get("TOKEN_ENCRYPTION_KEY") or os.environ.get("MCP_CONNECT_SECRET")
    if explicit:
        return hashlib.sha256(explicit.encode()).digest()
    is_testing = "PYTEST_CURRENT_TEST" in os.environ or os.environ.get("TESTING", "").lower() == "true"
    if not config.DEBUG and not is_testing:
        raise RuntimeError(
            "TOKEN_ENCRYPTION_KEY or MCP_CONNECT_SECRET is required in production mode "
            "to sign OAuth state tokens."
        )
    return hashlib.sha256(b"kairos-oauth-state-signing-fallback").digest()

def _sim_codes_allowed() -> bool:
    """Simulated OAuth codes (code=sim-*-code) are a dev/demo convenience only.
    In production they must be rejected: the Jira sim path in particular would
    otherwise write the deployer's REAL global JIRA_API_TOKEN into any calling
    user's oauth_tokens row (zoom_callback already had this check; slack/gmail/
    jira did not)."""
    is_testing = "PYTEST_CURRENT_TEST" in os.environ or os.environ.get("TESTING", "").lower() == "true"
    return config.DEBUG or is_testing


def _generate_state_token(uid: str) -> str:
    """Generates a signed state token containing the user UID and an expiry timestamp."""
    expires = int(time.time()) + 600  # 10 minutes expiry
    payload = f"{uid}:{expires}"
    sig = hmac.new(_oauth_signing_key(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}:{sig}"

def _verify_state_token(state: str) -> str | None:
    """Verifies the signed state token and returns user UID if valid. Uses rsplit to handle colons in UIDs."""
    try:
        parts = state.rsplit(":", 2)
        if len(parts) != 3:
            return None
        uid, expires_str, sig = parts
        expires = int(expires_str)
        if time.time() > expires:
            return None  # Token expired
        payload = f"{uid}:{expires_str}"
        expected_sig = hmac.new(_oauth_signing_key(), payload.encode(), hashlib.sha256).hexdigest()
        if hmac.compare_digest(sig, expected_sig):
            return uid
    except Exception:
        pass
    return None


# ── SQLite token store (piggybacks on kairos.db) ──────────────────────────────

def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(config.SQLITE_PATH, check_same_thread=False, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA busy_timeout=30000;")
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
            (user_uid, service, encrypt_token_data(token_data), datetime.utcnow().isoformat()),
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
        data = decrypt_token_data(row["token_data"])
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
    # Escape provider/user-controlled values (workspace name, email) — they are
    # rendered into HTML on the backend origin, so unescaped values are XSS.
    service_s = html.escape((service or "").upper())
    detail_s = html.escape(detail or "")
    page = f"""<!DOCTYPE html><html><head><title>KAIROS</title>
<style>{_POPUP_STYLE}</style></head><body>
<div class="card">
  <div class="dot green"></div>
  <strong>{service_s} CONNECTED</strong>
  <small>{detail_s}</small>
  <small style="color:#52525b;margin-top:10px;">Closing window…</small>
</div>
<script>setTimeout(() => window.close(), 1500);</script>
</body></html>"""
    return HTMLResponse(content=page)


def _popup_error(msg: str) -> HTMLResponse:
    # Escape the message — it can be a reflected `error` query param or a
    # provider-returned error string (reflected XSS otherwise).
    msg_s = html.escape(msg or "")
    page = f"""<!DOCTYPE html><html><head><title>KAIROS</title>
<style>{_POPUP_STYLE}</style></head><body>
<div class="card" style="border-color:#7f1d1d;">
  <div class="dot red"></div>
  <strong style="color:#ef4444;">Connection Failed</strong>
  <small>{msg_s}</small>
  <small style="color:#52525b;margin-top:10px;">Closing window…</small>
</div>
<script>setTimeout(() => window.close(), 3000);</script>
</body></html>"""
    return HTMLResponse(content=page, status_code=400)


def _callback_url(service: str) -> str:
    """Redirect URI registered in each OAuth app — points to this backend.

    Falls back to the deployed HF Space URL when BACKEND_URL is unset or
    still pointing at localhost, so a misconfigured/missing env var never
    sends a provider a redirect_uri they can't reach in production.
    """
    backend = config.BACKEND_URL
    if not backend or "localhost" in backend or "127.0.0.1" in backend:
        backend = "https://baljot07-kairos-backend.hf.space"
    return f"{backend}/api/oauth/{service}/callback"


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
        if not _sim_codes_allowed():
            return _popup_error("Simulated connections are not allowed in production.")
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
        "https://www.googleapis.com/auth/documents.readonly",
        "https://www.googleapis.com/auth/userinfo.email",
    ])
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
        if not _sim_codes_allowed():
            return _popup_error("Simulated connections are not allowed in production.")
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


# ── GITHUB ────────────────────────────────────────────────────────────────────

@router.get("/github/start")
async def github_start(current_user: UserProfile = Depends(get_current_user)):
    state = _generate_state_token(current_user.uid)
    if not config.GITHUB_CLIENT_ID or config.GITHUB_CLIENT_ID == "your_client_id":
        sim_url = f"{_callback_url('github')}?code=sim-github-code&state={state}"
        return {"service": "github", "url": sim_url}

    # "repo" covers private+public repo read access (GitHub OAuth Apps only
    # offer coarse scopes — there's no read-only-repo scope, only GitHub Apps
    # have per-permission granularity). "read:user" is for the display name.
    scopes = "repo read:user"
    url = (
        "https://github.com/login/oauth/authorize"
        f"?client_id={config.GITHUB_CLIENT_ID}"
        f"&redirect_uri={quote(_callback_url('github'), safe='')}"
        f"&scope={quote(scopes)}"
        f"&state={state}"
    )
    return {"service": "github", "url": url}


@router.get("/github/callback")
async def github_callback(code: str = None, state: str = None, error: str = None):
    if error or not code or not state:
        return _popup_error(error or "Missing authorization code")

    verified_uid = _verify_state_token(state)
    if not verified_uid:
        return _popup_error("Security Check Failed: Invalid or expired OAuth state parameter.")

    if code == "sim-github-code":
        if not _sim_codes_allowed():
            return _popup_error("Simulated connections are not allowed in production.")
        username = "helios-dev (Simulated)"
        _store_token(verified_uid, "github", {
            "access_token": "sim-github-token-12345",
            "username": username,
            "service": "github",
        })
        print(f"[OAuth] ✅ Simulated GitHub connected uid={verified_uid} user={username}")
        return _popup_success("GitHub", f"Connected as {username} (Simulation)")

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://github.com/login/oauth/access_token",
                headers={"Accept": "application/json"},
                data={
                    "client_id": config.GITHUB_CLIENT_ID,
                    "client_secret": config.GITHUB_CLIENT_SECRET,
                    "code": code,
                    "redirect_uri": _callback_url("github"),
                },
            )
            data = resp.json()
            if "error" in data:
                return _popup_error(data.get("error_description") or data["error"])

            access_token = data.get("access_token")
            if not access_token:
                return _popup_error("GitHub did not return an access token.")

            username = "your account"
            try:
                user_resp = await client.get(
                    "https://api.github.com/user",
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Accept": "application/vnd.github+json",
                    },
                )
                username = user_resp.json().get("login", username)
            except Exception:
                pass

        _store_token(verified_uid, "github", {
            "access_token": access_token,
            "username": username,
            "service": "github",
        })
        print(f"[OAuth] ✅ GitHub connected uid={verified_uid} user={username}")
        return _popup_success("GitHub", f"Connected as {username}")

    except Exception as e:
        print(f"[OAuth] 🔴 GitHub callback error: {e}")
        return _popup_error("We couldn't complete the connection. Please try again.")


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
        # Extra-sensitive: this branch stores the deployer's REAL global Jira
        # credential (JIRA_API_TOKEN) into the calling user's row — never in prod.
        if not _sim_codes_allowed():
            return _popup_error("Simulated connections are not allowed in production.")
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

        # Atlassian 3LO OAuth tokens are scoped to a set of accessible sites,
        # not a single fixed URL — resolve which Jira Cloud site (cloud_id)
        # this token can actually read, since every API call has to go
        # through https://api.atlassian.com/ex/jira/{cloud_id}/... rather
        # than the site's own domain. Without this, the stored token has no
        # cloud_id and jira_connector.py can't use it at all.
        from connectors.jira_connector import JiraConnector
        site = await JiraConnector.resolve_accessible_site(data.get("access_token"))
        if not site or not site.get("cloud_id"):
            return _popup_error(
                "Connected, but no accessible Jira site was found — make sure you "
                "granted access to a site during authorization, then try again."
            )

        _store_token(verified_uid, "jira", {
            "access_token": data.get("access_token"),
            "refresh_token": data.get("refresh_token"),
            "cloud_id": site.get("cloud_id"),
            "workspace": site.get("name") or site.get("url") or "Jira",
            "email": email,
            "service": "jira",
        })
        print(f"[OAuth] ✅ Jira connected uid={verified_uid} email={email} site={site.get('name')}")
        return _popup_success("Jira", f"Connected as {email} ({site.get('name') or 'Jira'})")

    except Exception as e:
        print(f"[OAuth] 🔴 Jira callback error: {e}")
        return _popup_error("We couldn't complete the connection. Please try again.")


# ── ZOOM ──────────────────────────────────────────────────────────────────────

# ── NOTION ────────────────────────────────────────────────────────────────────

@router.get("/notion/start")
async def notion_start(current_user: UserProfile = Depends(get_current_user)):
    state = _generate_state_token(current_user.uid)
    url = (
        "https://api.notion.com/v1/oauth/authorize"
        f"?client_id={config.NOTION_CLIENT_ID}"
        "&response_type=code"
        "&owner=user"
        f"&redirect_uri={quote(_callback_url('notion'), safe='')}"
        f"&state={state}"
    )
    return {"service": "notion", "url": url}


@router.get("/notion/callback")
async def notion_callback(code: str = None, state: str = None, error: str = None):
    if error or not code or not state:
        return _popup_error(error or "Missing authorization code")

    verified_uid = _verify_state_token(state)
    if not verified_uid:
        return _popup_error("Security Check Failed: Invalid or expired OAuth state parameter.")

    try:
        credentials = base64.b64encode(
            f"{config.NOTION_CLIENT_ID}:{config.NOTION_CLIENT_SECRET}".encode()
        ).decode()

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                "https://api.notion.com/v1/oauth/token",
                headers={
                    "Authorization": f"Basic {credentials}",
                    "Content-Type": "application/json",
                    "Notion-Version": "2022-06-28",
                },
                json={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": _callback_url("notion"),
                },
            )

        if resp.status_code != 200:
            print(f"[OAuth] 🔴 Notion token exchange failed: {resp.status_code} {resp.text}")
            return _popup_error("Notion authorization failed — please try again.")

        data = resp.json()
        access_token = data.get("access_token")
        workspace_name = data.get("workspace_name") or "Notion Workspace"
        workspace_id = data.get("workspace_id", "")

        if not access_token:
            return _popup_error("Notion did not return an access token.")

        _store_token(verified_uid, "notion", {
            "access_token": access_token,
            "workspace_name": workspace_name,
            "workspace_id": workspace_id,
            "service": "notion",
            "connected_at": datetime.utcnow().isoformat(),
        })
        print(f"[OAuth] ✅ Notion connected uid={verified_uid} workspace={workspace_name}")
        return _popup_success("Notion", f"Connected to {workspace_name}")

    except Exception as e:
        print(f"[OAuth] 🔴 Notion callback error: {e}")
        return _popup_error("We couldn't complete the Notion connection. Please try again.")


@router.get("/zoom/start")
async def zoom_start(current_user: UserProfile = Depends(get_current_user)):
    state = _generate_state_token(current_user.uid)

    # Server-to-Server app (account_credentials grant): there is NO user consent
    # screen for this grant type, so opening a popup would just flash our own
    # callback. Connect server-side immediately and tell the frontend it's done
    # (no `url` → the button skips the popup and refreshes to "Connected").
    # This is ONE global account credential for the whole deployment (like
    # Jira), so — same as Jira — only auto-connect it for the designated
    # owner uid. Every other user falls through to the real per-user OAuth
    # popup below instead of silently inheriting the deployer's own Zoom.
    if (
        config.ZOOM_ACCOUNT_ID and config.ZOOM_CLIENT_ID and config.ZOOM_CLIENT_SECRET
        and current_user.uid == config.ZOOM_OWNER_UID
    ):
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

    # No real per-user OAuth app configured (and not the S2S owner) →
    # simulated connect (demo mode) rather than granting anyone else the
    # global Zoom account.
    if not config.ZOOM_CLIENT_ID or config.ZOOM_CLIENT_ID == "your_client_id":
        sim_url = f"{_callback_url('zoom')}?code=sim-zoom-code&state={state}"
        return {"service": "zoom", "url": sim_url}

    # User-managed OAuth app → real Zoom consent popup (redirect_uri URL-encoded).
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

    is_testing = "PYTEST_CURRENT_TEST" in os.environ or os.environ.get("TESTING") == "true" or os.environ.get("TESTING") == "True"
    if code == "sim-zoom-code":
        if not config.DEBUG and not is_testing:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Simulated codes are not allowed in production mode."
            )
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

        expires_in = data.get("expires_in", 3599)
        _store_token(verified_uid, "zoom", {
            "access_token": data.get("access_token"),
            "refresh_token": data.get("refresh_token"),
            "expires_in": expires_in,
            "expires_at": int(time.time()) + expires_in,
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
        "jira": "jira", "zoom": "zoom", "notion": "notion", "github": "github",
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
    valid = {"slack", "gmail", "drive", "jira", "zoom", "notion", "github"}
    if service not in valid:
        raise HTTPException(400, f"Unknown service: {service}")
    # "gmail" and "drive" both map to the single "google" grant in the token store
    storage_key = "google" if service in ("gmail", "drive") else service
    # Mark as disconnected in DB to prevent re-inheriting env fallback
    _store_token(current_user.uid, storage_key, {"disconnected": True})
    print(f"[OAuth] 🔓 {service} disconnected uid={current_user.uid}")
    return {"status": "disconnected", "service": service}
