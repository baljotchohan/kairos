"""Tests for core/mcp_auth.py — per-user MCP connect token minting,
verification, and epoch-based revocation.

MCP tokens are deterministic and have no time-based expiry (mint_mcp_token(uid)
always returns the same string for the same uid+epoch), so "revocation" can't
work by blacklisting a single issued token — it works by bumping a per-user
epoch embedded in the token, invalidating everything issued at the old epoch.
"""

import sqlite3

import pytest

from core.mcp_auth import mint_mcp_token, verify_mcp_token, revoke_mcp_tokens, _sign_legacy


@pytest.fixture(autouse=True)
def _isolated_sqlite(tmp_path, monkeypatch):
    """Redirect config.SQLITE_PATH so epoch state never touches the real dev DB."""
    from config import config
    monkeypatch.setattr(config, "SQLITE_PATH", str(tmp_path / "mcp_auth_test.db"))
    monkeypatch.setenv("MCP_CONNECT_SECRET", "test-secret-for-mcp-auth-tests")
    yield


def test_mint_and_verify_round_trip():
    token = mint_mcp_token("user-a")
    assert verify_mcp_token(token) == "user-a"


def test_verify_rejects_tampered_signature():
    token = mint_mcp_token("user-a")
    uid_b64, epoch, sig = token.split(".")
    tampered = f"{uid_b64}.{epoch}.{'0' * len(sig)}"
    assert verify_mcp_token(tampered) is None


def test_verify_rejects_garbage_token():
    assert verify_mcp_token("not-a-real-token") is None
    assert verify_mcp_token("") is None
    assert verify_mcp_token(None) is None


def test_legacy_two_part_token_still_verifies_at_epoch_zero():
    """Backward compatibility: tokens minted before revocation existed used a
    2-part format (uid_b64.sig) with no embedded epoch. They must keep
    working for a user who has never revoked (epoch still 0)."""
    from core.mcp_auth import _secret
    import base64

    user_id = "legacy-user"
    uid_b64 = base64.urlsafe_b64encode(user_id.encode()).decode().rstrip("=")
    legacy_token = f"{uid_b64}.{_sign_legacy(user_id)}"

    assert verify_mcp_token(legacy_token) == user_id


def test_revoke_invalidates_previously_issued_token():
    token = mint_mcp_token("user-a")
    assert verify_mcp_token(token) == "user-a"

    revoke_mcp_tokens("user-a")

    assert verify_mcp_token(token) is None


def test_revoke_also_invalidates_legacy_format_tokens():
    from core.mcp_auth import _secret
    import base64

    user_id = "legacy-user-2"
    uid_b64 = base64.urlsafe_b64encode(user_id.encode()).decode().rstrip("=")
    legacy_token = f"{uid_b64}.{_sign_legacy(user_id)}"
    assert verify_mcp_token(legacy_token) == user_id

    revoke_mcp_tokens(user_id)

    assert verify_mcp_token(legacy_token) is None


def test_newly_minted_token_after_revoke_works():
    old_token = mint_mcp_token("user-a")
    revoke_mcp_tokens("user-a")
    assert verify_mcp_token(old_token) is None

    new_token = mint_mcp_token("user-a")
    assert new_token != old_token
    assert verify_mcp_token(new_token) == "user-a"


def test_revoke_only_affects_the_named_user():
    token_a = mint_mcp_token("user-a")
    token_b = mint_mcp_token("user-b")

    revoke_mcp_tokens("user-a")

    assert verify_mcp_token(token_a) is None
    assert verify_mcp_token(token_b) == "user-b"


def test_revoke_is_idempotent_and_safe_to_call_repeatedly():
    token1 = mint_mcp_token("user-a")
    revoke_mcp_tokens("user-a")
    token2 = mint_mcp_token("user-a")
    revoke_mcp_tokens("user-a")
    token3 = mint_mcp_token("user-a")

    assert verify_mcp_token(token1) is None
    assert verify_mcp_token(token2) is None
    assert verify_mcp_token(token3) == "user-a"
