"""
Per-user MCP connect tokens.

A KAIROS user connects Claude Desktop / Claude (web/mobile) / ChatGPT / Cursor to
THEIR OWN organizational memory by adding a single remote MCP URL that embeds a
signed, per-user token:

    https://<backend>/mcp/u/<token>

The remote MCP endpoint (api/routes/mcp_remote.py) verifies the token on every
JSON-RPC call and scopes every tool to that user's data — so one shared server
serves many users without leaking across them.

Token = urlsafe_b64(user_id) + "." + epoch + "." + HMAC-SHA256(secret, f"{user_id}:{epoch}")[:40]

The signing secret MUST be stable across restarts (the token is a long-lived
connector credential, like an API key), so it is read from MCP_CONNECT_SECRET and
falls back to a value derived deterministically from existing stable secrets.
Set MCP_CONNECT_SECRET explicitly in any real deployment.

Revocation: each user has a token "epoch" (default 0, stored in the shared
SQLite file). mint_mcp_token() always embeds the user's CURRENT epoch; a token
only verifies if its embedded epoch still matches. revoke_mcp_tokens(user_id)
bumps the epoch, instantly invalidating every previously-issued token for that
user (both URL tokens and OAuth-issued access tokens, since both paths call
mint_mcp_token/verify_mcp_token) without affecting any other user or requiring
a global secret rotation. Tokens minted before this existed have no embedded
epoch (2-part legacy format) and are treated as epoch 0 for backward
compatibility — they keep working until the user's first revoke, same as any
other epoch-0 token.

This is the pragmatic per-user path; the "proper" upgrade is full OAuth 2.1 +
dynamic client registration per the MCP authorization spec (see docs/REMOTE_MCP.md).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import sqlite3
import time


def _epoch_connect(sqlite_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(sqlite_path, timeout=30.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA busy_timeout=30000;")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS mcp_token_epochs (
            user_id    TEXT PRIMARY KEY,
            epoch      INTEGER NOT NULL DEFAULT 0,
            updated_at REAL
        )
    """)
    return conn


def _get_epoch(user_id: str) -> int:
    """Current token epoch for user_id (0 = never revoked)."""
    from config import config
    # sqlite3.Connection's own context-manager protocol only commits/rolls
    # back the transaction on exit — it never closes the connection, so
    # `with _epoch_connect(...) as conn:` used to leak a file descriptor on
    # every call (this runs on every single remote MCP tool invocation).
    conn = None
    try:
        conn = _epoch_connect(config.SQLITE_PATH)
        row = conn.execute("SELECT epoch FROM mcp_token_epochs WHERE user_id = ?", (user_id,)).fetchone()
        return row[0] if row else 0
    except Exception:
        # Fail open to epoch 0 rather than locking every user out if the
        # epochs table is momentarily unreachable — matches this token
        # scheme's existing "persistent credential" trust model.
        return 0
    finally:
        if conn is not None:
            conn.close()


def revoke_mcp_tokens(user_id: str) -> int:
    """Bump user_id's token epoch, invalidating every previously-issued MCP
    token for them (URL tokens and OAuth access tokens alike). Returns the
    new epoch. A user calling this again before minting a new token is a
    harmless no-op re-bump (still invalidates everything issued so far)."""
    from config import config
    conn = _epoch_connect(config.SQLITE_PATH)
    try:
        conn.execute("""
            INSERT INTO mcp_token_epochs (user_id, epoch, updated_at) VALUES (?, 1, ?)
            ON CONFLICT(user_id) DO UPDATE SET epoch = epoch + 1, updated_at = excluded.updated_at
        """, (user_id, time.time()))
        conn.commit()
        return conn.execute("SELECT epoch FROM mcp_token_epochs WHERE user_id = ?", (user_id,)).fetchone()[0]
    finally:
        conn.close()


def _secret() -> bytes:
    explicit = os.environ.get("MCP_CONNECT_SECRET")
    if explicit:
        return explicit.encode()
    from config import config
    is_testing = "PYTEST_CURRENT_TEST" in os.environ or os.environ.get("TESTING") == "true" or os.environ.get("TESTING") == "True"
    if not config.DEBUG and not is_testing:
        raise RuntimeError("MCP_CONNECT_SECRET environment variable is required in production mode.")
    # Deterministic fallback so already-issued connect URLs keep working across
    # restarts even when MCP_CONNECT_SECRET isn't set (dev/demo). Derived from a
    # stable existing secret.
    base = (
        getattr(config, "FIREWORKS_API_KEY", "")
        or getattr(config, "GOOGLE_CLIENT_SECRET", "")
        or "kairos-dev-mcp-secret"
    )
    return hashlib.sha256(f"kairos-mcp::{base}".encode()).digest()


def _sign(user_id: str, epoch: int) -> str:
    return hmac.new(_secret(), f"{user_id}:{epoch}".encode(), hashlib.sha256).hexdigest()[:40]


def _sign_legacy(user_id: str) -> str:
    """Pre-revocation signature scheme (no epoch) — see module docstring."""
    return hmac.new(_secret(), user_id.encode(), hashlib.sha256).hexdigest()[:40]


def mint_mcp_token(user_id: str) -> str:
    """Create a signed connect token for a user, bound to their current
    revocation epoch (no time-based expiry — this is a persistent credential,
    like an API key, revoked explicitly via revoke_mcp_tokens())."""
    epoch = _get_epoch(user_id)
    uid_b64 = base64.urlsafe_b64encode(user_id.encode()).decode().rstrip("=")
    return f"{uid_b64}.{epoch}.{_sign(user_id, epoch)}"


def verify_mcp_token(token: str) -> str | None:
    """Return the user_id if the token's signature is valid AND its epoch
    hasn't been revoked since it was minted, else None."""
    if not token or "." not in token:
        return None
    parts = token.split(".")
    try:
        if len(parts) == 3:
            uid_b64, epoch_str, sig = parts
            epoch = int(epoch_str)
            padding = "=" * (-len(uid_b64) % 4)
            user_id = base64.urlsafe_b64decode(uid_b64 + padding).decode()
            if not hmac.compare_digest(sig, _sign(user_id, epoch)):
                return None
        elif len(parts) == 2:
            # Legacy 2-part token minted before revocation existed — treat as epoch 0.
            uid_b64, sig = parts
            padding = "=" * (-len(uid_b64) % 4)
            user_id = base64.urlsafe_b64decode(uid_b64 + padding).decode()
            if not hmac.compare_digest(sig, _sign_legacy(user_id)):
                return None
            epoch = 0
        else:
            return None
    except Exception:
        return None

    if epoch != _get_epoch(user_id):
        return None
    return user_id
