"""Tests for GET /admin/mcp-activity — the real backing data for the
dashboard's "Activity Monitor" panel, which previously rendered a
hardcoded/simulated log with no real data behind it."""

import pytest
from fastapi.testclient import TestClient

from api.main import app
from config import config
from core.mcp_telemetry import log_tool_call


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "SQLITE_PATH", str(tmp_path / "admin_activity_test.db"))
    with TestClient(app) as c:
        yield c


TEST_UID = "sim-guest-uid-activity"  # "simulated-guest-activity" -> this uid, see api/auth.py


def _auth_headers():
    return {"Authorization": "Bearer simulated-guest-activity"}


def test_mcp_activity_reflects_real_logged_calls(client):
    log_tool_call(TEST_UID, "get_context", transport="stdio", client_name="Claude Desktop", status="success")
    log_tool_call(TEST_UID, "store_context", transport="remote", client_name="ChatGPT", status="success")

    resp = client.get("/api/admin/mcp-activity", headers=_auth_headers())

    assert resp.status_code == 200
    data = resp.json()
    tool_names = {log["tool"] for log in data["logs"]}
    assert tool_names == {"get_context", "store_context"}
    assert data["stats"]["totalRequests"] == 2
    assert data["stats"]["writeOps"] == 1
    assert data["stats"]["readOps"] == 1


def test_mcp_activity_is_empty_for_a_user_with_no_calls(client):
    resp = client.get("/api/admin/mcp-activity", headers=_auth_headers())

    assert resp.status_code == 200
    data = resp.json()
    assert data["logs"] == []
    assert data["stats"]["totalRequests"] == 0


def test_mcp_activity_never_shows_another_users_calls(client):
    log_tool_call("some-other-user", "get_context", transport="stdio", status="success")

    resp = client.get("/api/admin/mcp-activity", headers=_auth_headers())

    assert resp.status_code == 200
    assert resp.json()["logs"] == []
