"""
MCP OAuth 2.0 Authorization Server for KAIROS.

Claude.ai's custom connector platform REQUIRES OAuth 2.0 with dynamic client
registration (RFC 7591). This implements the minimal correct flow:

  1. GET  /.well-known/oauth-authorization-server  → discovery doc
  2. POST /oauth/register                          → register Claude as a client
  3. GET  /oauth/authorize?...                     → store params, redirect to /oauth/login
  4. POST /api/mcp/oauth/complete                  → frontend sends Firebase JWT → issues code
  5. POST /oauth/token                             → exchange code for access token

Access tokens use the same HMAC-signed format as URL tokens so the MCP
Bearer endpoint verifies them with the existing verify_mcp_token().
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import sqlite3
import uuid
from datetime import datetime

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, RedirectResponse

from config import config
from core.mcp_auth import mint_mcp_token

# Public routes mounted at root: /.well-known/*, /oauth/*
mcp_oauth_public_router = APIRouter(tags=["mcp-oauth"])
# API routes mounted under /api: /api/mcp/oauth/*
mcp_oauth_api_router = APIRouter(prefix="/mcp/oauth", tags=["mcp-oauth"])


# ── SQLite helpers ─────────────────────────────────────────────────────────────

def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(config.SQLITE_PATH, check_same_thread=False, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA busy_timeout=30000;")
    for stmt in [
        """CREATE TABLE IF NOT EXISTS mcp_oauth_clients (
               client_id    TEXT PRIMARY KEY,
               redirect_uris TEXT NOT NULL,
               created_at   TEXT NOT NULL
           )""",
        """CREATE TABLE IF NOT EXISTS mcp_oauth_requests (
               req_id         TEXT PRIMARY KEY,
               client_id      TEXT NOT NULL,
               redirect_uri   TEXT NOT NULL,
               code_challenge TEXT,
               state          TEXT,
               created_at     TEXT NOT NULL
           )""",
        """CREATE TABLE IF NOT EXISTS mcp_oauth_codes (
               code           TEXT PRIMARY KEY,
               user_id        TEXT NOT NULL,
               client_id      TEXT NOT NULL,
               redirect_uri   TEXT NOT NULL,
               code_challenge TEXT,
               state          TEXT,
               created_at     TEXT NOT NULL,
               used           INTEGER DEFAULT 0
           )""",
    ]:
        conn.execute(stmt)
    conn.commit()
    return conn


def _base_url(request: Request) -> str:
    scheme = request.headers.get("x-forwarded-proto", request.url.scheme)
    host = request.headers.get("x-forwarded-host", request.url.netloc)
    return f"{scheme}://{host}"


# ── 1. Discovery ───────────────────────────────────────────────────────────────

@mcp_oauth_public_router.get("/.well-known/oauth-authorization-server")
async def oauth_discovery(request: Request):
    base = _base_url(request)
    return JSONResponse({
        "issuer": base,
        "authorization_endpoint": f"{base}/oauth/authorize",
        "token_endpoint": f"{base}/oauth/token",
        "registration_endpoint": f"{base}/oauth/register",
        "scopes_supported": ["mcp"],
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code"],
        "code_challenge_methods_supported": ["S256"],
        "token_endpoint_auth_methods_supported": ["none"],
    })


# ── 2. Dynamic Client Registration (RFC 7591) ──────────────────────────────────

@mcp_oauth_public_router.post("/oauth/register")
async def oauth_register(request: Request):
    try:
        body = await request.json()
    except Exception:
        body = {}

    client_id = uuid.uuid4().hex
    redirect_uris = body.get("redirect_uris", [])

    c = _conn()
    try:
        c.execute(
            "INSERT INTO mcp_oauth_clients (client_id, redirect_uris, created_at) VALUES (?, ?, ?)",
            (client_id, json.dumps(redirect_uris), datetime.utcnow().isoformat()),
        )
        c.commit()
    finally:
        c.close()

    return JSONResponse({
        "client_id": client_id,
        "redirect_uris": redirect_uris,
        "grant_types": ["authorization_code"],
        "response_types": ["code"],
        "token_endpoint_auth_method": "none",
    }, status_code=201)


# ── 3. Authorization Endpoint ──────────────────────────────────────────────────

@mcp_oauth_public_router.get("/oauth/authorize")
async def oauth_authorize(request: Request):
    p = dict(request.query_params)
    redirect_uri = p.get("redirect_uri", "")

    if not redirect_uri:
        return JSONResponse({"error": "invalid_request", "error_description": "redirect_uri required"}, status_code=400)

    req_id = uuid.uuid4().hex
    c = _conn()
    try:
        c.execute(
            "INSERT INTO mcp_oauth_requests (req_id, client_id, redirect_uri, code_challenge, state, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (req_id, p.get("client_id", ""), redirect_uri, p.get("code_challenge", ""), p.get("state", ""), datetime.utcnow().isoformat()),
        )
        c.commit()
    finally:
        c.close()

    # Redirect user's browser to the KAIROS login page.
    # Use base_url from the request (Vercel domain) not config.FRONTEND_URL
    # (which may be localhost in the HF Space env).
    base = _base_url(request)
    return RedirectResponse(f"{base}/oauth/login?req_id={req_id}", status_code=302)


# ── 4. Complete (frontend calls this after Firebase sign-in) ───────────────────

@mcp_oauth_api_router.post("/complete")
async def oauth_complete(request: Request):
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid_request"}, status_code=400)

    firebase_token = body.get("firebase_token", "")
    req_id = body.get("req_id", "")

    if not firebase_token or not req_id:
        return JSONResponse({"error": "invalid_request", "error_description": "firebase_token and req_id required"}, status_code=400)

    try:
        from api.auth import verify_token
        profile = verify_token(firebase_token)
        user_id = profile.uid
    except Exception:
        return JSONResponse({"error": "invalid_token", "error_description": "Firebase token verification failed"}, status_code=401)

    if not user_id:
        return JSONResponse({"error": "invalid_token"}, status_code=401)

    c = _conn()
    try:
        row = c.execute("SELECT * FROM mcp_oauth_requests WHERE req_id = ?", (req_id,)).fetchone()
        if not row:
            return JSONResponse({"error": "invalid_request", "error_description": "OAuth request not found or expired"}, status_code=400)

        # 15-minute window to complete sign-in
        created_at = datetime.fromisoformat(row["created_at"])
        if (datetime.utcnow() - created_at).total_seconds() > 900:
            c.execute("DELETE FROM mcp_oauth_requests WHERE req_id = ?", (req_id,))
            c.commit()
            return JSONResponse({"error": "invalid_request", "error_description": "OAuth request expired, please try again"}, status_code=400)

        code = uuid.uuid4().hex
        c.execute(
            "INSERT INTO mcp_oauth_codes (code, user_id, client_id, redirect_uri, code_challenge, state, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (code, user_id, row["client_id"], row["redirect_uri"], row["code_challenge"], row["state"], datetime.utcnow().isoformat()),
        )
        c.execute("DELETE FROM mcp_oauth_requests WHERE req_id = ?", (req_id,))
        c.commit()

        return JSONResponse({"code": code, "redirect_uri": row["redirect_uri"], "state": row["state"]})
    finally:
        c.close()


# ── 5. Token Endpoint ──────────────────────────────────────────────────────────

@mcp_oauth_public_router.post("/oauth/token")
async def oauth_token(request: Request):
    ct = request.headers.get("content-type", "")
    if "application/json" in ct:
        try:
            body = await request.json()
        except Exception:
            body = {}
    else:
        form = await request.form()
        body = dict(form)

    grant_type = body.get("grant_type", "")
    code = body.get("code", "")
    code_verifier = body.get("code_verifier", "")

    if grant_type != "authorization_code":
        return JSONResponse({"error": "unsupported_grant_type"}, status_code=400)
    if not code:
        return JSONResponse({"error": "invalid_request", "error_description": "code required"}, status_code=400)

    c = _conn()
    try:
        row = c.execute("SELECT * FROM mcp_oauth_codes WHERE code = ? AND used = 0", (code,)).fetchone()
        if not row:
            return JSONResponse({"error": "invalid_grant", "error_description": "Invalid or expired authorization code"}, status_code=400)

        created_at = datetime.fromisoformat(row["created_at"])
        if (datetime.utcnow() - created_at).total_seconds() > 600:
            return JSONResponse({"error": "invalid_grant", "error_description": "Authorization code expired"}, status_code=400)

        # Verify PKCE
        if row["code_challenge"] and code_verifier:
            challenge = base64.urlsafe_b64encode(
                hashlib.sha256(code_verifier.encode()).digest()
            ).decode().rstrip("=")
            if not hmac.compare_digest(challenge, row["code_challenge"]):
                return JSONResponse({"error": "invalid_grant", "error_description": "PKCE verification failed"}, status_code=400)

        c.execute("UPDATE mcp_oauth_codes SET used = 1 WHERE code = ?", (code,))
        c.commit()
        user_id = row["user_id"]
    finally:
        c.close()

    # Issue access token — same HMAC format as URL tokens, verified by verify_mcp_token()
    access_token = mint_mcp_token(user_id)

    return JSONResponse({
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": 31536000,
    })
