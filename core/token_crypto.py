"""
Envelope encryption for OAuth tokens stored in SQLite (oauth_tokens.token_data).

Tokens (Google refresh/access tokens, Slack bot tokens, Jira tokens, Zoom
client secrets) are long-lived, highly privileged secrets. Storing them as
plaintext JSON means anyone who can read kairos.db gets durable, replayable
access to every connected user's data. This module encrypts them with
Fernet (AES-128-CBC + HMAC) keyed from the TOKEN_ENCRYPTION_KEY env var.

Design:
  - encrypt_token_data(dict) -> str   (prefixed "enc:" when a key is configured)
  - decrypt_token_data(str)  -> dict  (transparently reads both encrypted and
                                        legacy-plaintext rows for backward compat)

Behaviour without TOKEN_ENCRYPTION_KEY:
  - Falls back to plaintext (dev/demo). Set the key in any real deployment.
  - Generate one with:  python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
"""

from __future__ import annotations

import os
import json

try:
    from cryptography.fernet import Fernet, InvalidToken
except Exception:  # cryptography not installed
    Fernet = None
    InvalidToken = Exception

_ENC_PREFIX = "enc:"


def _get_cipher():
    """Return a Fernet cipher if TOKEN_ENCRYPTION_KEY is set and valid, else None."""
    key = os.environ.get("TOKEN_ENCRYPTION_KEY")
    if not key or Fernet is None:
        return None
    try:
        return Fernet(key.encode())
    except Exception:
        return None


def encrypt_token_data(data: dict) -> str:
    """Serialize + encrypt a token dict for storage. Plaintext fallback if no key."""
    raw = json.dumps(data)
    cipher = _get_cipher()
    if cipher is None:
        return raw  # dev/demo: no key configured
    return _ENC_PREFIX + cipher.encrypt(raw.encode()).decode()


def decrypt_token_data(blob: str | None) -> dict:
    """Read a stored token blob, transparently handling encrypted + legacy plaintext."""
    if not blob:
        return {}
    if blob.startswith(_ENC_PREFIX):
        cipher = _get_cipher()
        if cipher is None:
            raise RuntimeError(
                "Encrypted OAuth token found but TOKEN_ENCRYPTION_KEY is missing/invalid."
            )
        try:
            raw = cipher.decrypt(blob[len(_ENC_PREFIX):].encode()).decode()
        except InvalidToken as e:
            raise RuntimeError("Failed to decrypt OAuth token (wrong key?).") from e
        return json.loads(raw)
    # Legacy plaintext row (pre-encryption) — still readable.
    return json.loads(blob)
