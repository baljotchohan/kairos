"""Tests for the MCP OAuth 2.0 + dynamic client registration flow
(api/routes/mcp_oauth.py) — specifically that /oauth/authorize validates
redirect_uri against what was registered for that client_id.

Without this check, client_ids aren't secret, so an attacker could reuse a
known client_id with their own redirect_uri, phish a real user into
authenticating, and have the authorization code delivered to an
attacker-controlled origin instead of the real client.
"""

import pytest
from fastapi.testclient import TestClient

from api.main import app
from config import config


@pytest.fixture
def oauth_client(tmp_path, monkeypatch):
    """TestClient with config.SQLITE_PATH redirected to a temp DB so these
    tests never touch the real dev/prod database."""
    monkeypatch.setattr(config, "SQLITE_PATH", str(tmp_path / "oauth_test.db"))
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


def _register(client, redirect_uris):
    resp = client.post("/oauth/register", json={"redirect_uris": redirect_uris})
    assert resp.status_code == 201
    return resp.json()["client_id"]


def test_register_returns_client_id(oauth_client):
    client_id = _register(oauth_client, ["https://real-client.example/callback"])
    assert client_id


def test_authorize_accepts_registered_redirect_uri(oauth_client):
    client_id = _register(oauth_client, ["https://real-client.example/callback"])
    resp = oauth_client.get(
        "/oauth/authorize",
        params={
            "client_id": client_id,
            "redirect_uri": "https://real-client.example/callback",
            "state": "xyz",
            "code_challenge": "abc123",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert "/oauth/login?req_id=" in resp.headers["location"]


def test_authorize_rejects_unregistered_client_id(oauth_client):
    resp = oauth_client.get(
        "/oauth/authorize",
        params={"client_id": "never-registered", "redirect_uri": "https://evil.example/steal", "code_challenge": "abc123"},
        follow_redirects=False,
    )
    assert resp.status_code == 400
    assert resp.json()["error"] == "invalid_client"


def test_authorize_rejects_redirect_uri_not_registered_for_that_client(oauth_client):
    """The core fix: a real, registered client_id combined with an
    attacker-supplied redirect_uri must be rejected, not silently accepted."""
    client_id = _register(oauth_client, ["https://real-client.example/callback"])
    resp = oauth_client.get(
        "/oauth/authorize",
        params={"client_id": client_id, "redirect_uri": "https://evil.example/steal", "code_challenge": "abc123"},
        follow_redirects=False,
    )
    assert resp.status_code == 400
    assert resp.json()["error"] == "invalid_request"


def test_authorize_requires_client_id(oauth_client):
    resp = oauth_client.get(
        "/oauth/authorize",
        params={"redirect_uri": "https://real-client.example/callback", "code_challenge": "abc123"},
        follow_redirects=False,
    )
    assert resp.status_code == 400


def test_authorize_requires_redirect_uri(oauth_client):
    client_id = _register(oauth_client, ["https://real-client.example/callback"])
    resp = oauth_client.get(
        "/oauth/authorize",
        params={"client_id": client_id, "code_challenge": "abc123"},
        follow_redirects=False,
    )
    assert resp.status_code == 400


def test_authorize_requires_code_challenge(oauth_client):
    """PKCE is mandatory — an authorize request with no code_challenge must
    be rejected rather than silently proceeding without PKCE protection."""
    client_id = _register(oauth_client, ["https://real-client.example/callback"])
    resp = oauth_client.get(
        "/oauth/authorize",
        params={"client_id": client_id, "redirect_uri": "https://real-client.example/callback"},
        follow_redirects=False,
    )
    assert resp.status_code == 400
    assert resp.json()["error"] == "invalid_request"
