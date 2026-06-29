"""
Per-user MCP connect tokens.

A KAIROS user connects Claude Desktop / Claude (web/mobile) / ChatGPT / Cursor to
THEIR OWN organizational memory by adding a single remote MCP URL that embeds a
signed, per-user token:

    https://<backend>/mcp/u/<token>

The remote MCP endpoint (api/routes/mcp_remote.py) verifies the token on every
JSON-RPC call and scopes every tool to that user's data — so one shared server
serves many users without leaking across them.

Token = urlsafe_b64(user_id) + "." + HMAC-SHA256(secret, user_id)[:40]

The signing secret MUST be stable across restarts (the token is a long-lived
connector credential, like an API key), so it is read from MCP_CONNECT_SECRET and
falls back to a value derived deterministically from existing stable secrets.
Set MCP_CONNECT_SECRET explicitly in any real deployment.

This is the pragmatic per-user path; the "proper" upgrade is full OAuth 2.1 +
dynamic client registration per the MCP authorization spec (see docs/REMOTE_MCP.md).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os


def _secret() -> bytes:
    explicit = os.environ.get("MCP_CONNECT_SECRET")
    if explicit:
        return explicit.encode()
    # Deterministic fallback so already-issued connect URLs keep working across
    # restarts even when MCP_CONNECT_SECRET isn't set (dev/demo). Derived from a
    # stable existing secret; documented to be overridden in production.
    from config import config
    base = (
        os.environ.get("MCP_CONNECT_SECRET")
        or getattr(config, "FIREWORKS_API_KEY", "")
        or getattr(config, "GOOGLE_CLIENT_SECRET", "")
        or "kairos-dev-mcp-secret"
    )
    return hashlib.sha256(f"kairos-mcp::{base}".encode()).digest()


def _sign(user_id: str) -> str:
    return hmac.new(_secret(), user_id.encode(), hashlib.sha256).hexdigest()[:40]


def mint_mcp_token(user_id: str) -> str:
    """Create a signed connect token for a user (no expiry — persistent credential)."""
    uid_b64 = base64.urlsafe_b64encode(user_id.encode()).decode().rstrip("=")
    return f"{uid_b64}.{_sign(user_id)}"


def verify_mcp_token(token: str) -> str | None:
    """Return the user_id if the token's signature is valid, else None."""
    if not token or "." not in token:
        return None
    try:
        uid_b64, sig = token.rsplit(".", 1)
        padding = "=" * (-len(uid_b64) % 4)
        user_id = base64.urlsafe_b64decode(uid_b64 + padding).decode()
    except Exception:
        return None
    if hmac.compare_digest(sig, _sign(user_id)):
        return user_id
    return None
