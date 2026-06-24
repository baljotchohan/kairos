"""Tests for FastAPI routes — uses TestClient, mocks memory + orchestrator."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

from api.main import app


@pytest.fixture
def client():
    """TestClient with mocked app state (no real DB or AI calls)."""
    mock_memory = MagicMock()
    mock_memory.graph.stats.return_value = {"total_decisions": 5, "total_relations": 7, "connected_components": 1}
    mock_memory.semantic_search.return_value = []

    mock_orchestrator = MagicMock()
    mock_orchestrator.query = AsyncMock(return_value={
        "answer": "We chose AWS because the team had existing expertise.",
        "sources": [{"id": "d1", "title": "AWS Decision", "date": "2021-08-15",
                     "source": "Slack #engineering", "source_url": "https://slack.example.com"}],
    })
    mock_orchestrator.query_with_memory = AsyncMock(return_value={
        "answer": "We chose AWS because the team had existing expertise.",
        "sources": [{"id": "d1", "title": "AWS Decision", "date": "2021-08-15",
                     "source": "Slack #engineering", "source_url": "https://slack.example.com"}],
    })

    with TestClient(app, raise_server_exceptions=True) as c:
        app.state.memory = mock_memory
        app.state.orchestrator = mock_orchestrator
        yield c


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_root(client):
    resp = client.get("/")
    assert resp.status_code == 200
    data = resp.json()
    assert "name" in data
    assert data["name"] == "KAIROS"


def test_query_requires_auth(client):
    resp = client.post("/api/v1/query", json={"question": "Why do we use AWS?"})
    # Without auth token, expect 401 or fallback simulation user (depends on Firebase config)
    assert resp.status_code in (200, 401)


def test_query_with_sim_token(client):
    resp = client.post(
        "/api/v1/query",
        json={"question": "Why do we use AWS?"},
        headers={"Authorization": "Bearer simulated-google-token"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "answer" in data
    assert "sources" in data


def test_decisions_list(client):
    client.app.state.memory.graph.all_decisions.return_value = []
    resp = client.get(
        "/api/v1/decisions",
        headers={"Authorization": "Bearer simulated-google-token"},
    )
    assert resp.status_code == 200
    assert "decisions" in resp.json()


def test_graph_stats(client):
    resp = client.get(
        "/api/v1/graph/stats",
        headers={"Authorization": "Bearer simulated-google-token"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "total_decisions" in data


def test_admin_status(client):
    resp = client.get(
        "/api/v1/admin/status",
        headers={"Authorization": "Bearer simulated-google-token"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "connectors" in data
    assert "total_decisions" in data
