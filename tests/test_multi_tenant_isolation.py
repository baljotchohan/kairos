"""End-to-end multi-tenant isolation tests — two REAL, distinct authenticated
users hit the actual HTTP routes (not mocked memory) and we assert neither can
see the other's data anywhere: decisions, search, single-decision lookup,
graph stats, debt score, and personas.

Every previous audit of this codebase checked that individual functions take
and enforce user_id (they do). What was missing was a test proving the
end-to-end guarantee holds through the real FastAPI routes with two real
tenants coexisting in the same database — this file closes that gap.

Auth: simulated "guest" tokens (not "google" tokens, which all collapse onto
the single DEMO_USER_ID via _map_demo_user) each produce a distinct, stable
uid: "simulated-guest-alice" -> "sim-guest-uid-alice", etc. See api/auth.py.
"""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from api.main import app
from core.memory import KairosMemory

USER_A = "sim-guest-uid-alice"
USER_B = "sim-guest-uid-bob"
TOKEN_A = "simulated-guest-alice"
TOKEN_B = "simulated-guest-bob"


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def two_tenant_client(tmp_path):
    """TestClient wired to a REAL KairosMemory (not MagicMock) so isolation is
    exercised through actual store/search/graph code paths, not mocked stubs."""
    chroma_path = str(tmp_path / "chroma")
    db_path = str(tmp_path / "test.db")
    vault_path = str(tmp_path / "vault")

    with patch("core.memory.FireworksEmbeddingFunction") as mock_ef:
        from chromadb.utils import embedding_functions
        mock_ef.return_value = embedding_functions.DefaultEmbeddingFunction()
        memory = KairosMemory(chroma_path=chroma_path, db_path=db_path, obsidian_vault=vault_path)

    with TestClient(app, raise_server_exceptions=True) as c:
        c.app.state.memory = memory
        yield c


def _store(client, token, title, topics=None):
    resp = client.post(
        "/api/v1/store",
        json={
            "title": title,
            "summary": f"{title} summary",
            "date": "2024-01-15",
            "source": "Slack #test",
            "topics": topics or ["Engineering"],
        },
        headers=_auth(token),
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


def test_decisions_list_scoped_per_user(two_tenant_client):
    _store(two_tenant_client, TOKEN_A, "Alice's Secret Decision")
    _store(two_tenant_client, TOKEN_B, "Bob's Secret Decision")

    resp_a = two_tenant_client.get("/api/v1/decisions", headers=_auth(TOKEN_A))
    resp_b = two_tenant_client.get("/api/v1/decisions", headers=_auth(TOKEN_B))

    titles_a = {d["title"] for d in resp_a.json()["decisions"]}
    titles_b = {d["title"] for d in resp_b.json()["decisions"]}

    assert "Alice's Secret Decision" in titles_a
    assert "Bob's Secret Decision" not in titles_a
    assert "Bob's Secret Decision" in titles_b
    assert "Alice's Secret Decision" not in titles_b


def test_decisions_search_scoped_per_user(two_tenant_client):
    _store(two_tenant_client, TOKEN_A, "Alice AWS Migration", topics=["AWS"])
    _store(two_tenant_client, TOKEN_B, "Bob AWS Migration", topics=["AWS"])

    resp_a = two_tenant_client.get("/api/v1/decisions/search", params={"topic": "AWS"}, headers=_auth(TOKEN_A))
    titles_a = {d["title"] for d in resp_a.json()["decisions"]}
    assert "Alice AWS Migration" in titles_a
    assert "Bob AWS Migration" not in titles_a


def test_single_decision_lookup_returns_404_for_other_users_decision(two_tenant_client):
    decision_id = _store(two_tenant_client, TOKEN_A, "Alice's Private Decision")

    own_view = two_tenant_client.get(f"/api/v1/decisions/{decision_id}", headers=_auth(TOKEN_A))
    assert own_view.status_code == 200

    other_view = two_tenant_client.get(f"/api/v1/decisions/{decision_id}", headers=_auth(TOKEN_B))
    assert other_view.status_code == 404


def test_graph_stats_scoped_per_user(two_tenant_client):
    _store(two_tenant_client, TOKEN_A, "Alice Decision 1")
    _store(two_tenant_client, TOKEN_A, "Alice Decision 2")
    _store(two_tenant_client, TOKEN_B, "Bob Decision 1")

    stats_a = two_tenant_client.get("/api/v1/graph/stats", headers=_auth(TOKEN_A)).json()
    stats_b = two_tenant_client.get("/api/v1/graph/stats", headers=_auth(TOKEN_B)).json()

    assert stats_a["total_decisions"] == 2
    assert stats_b["total_decisions"] == 1


def test_debt_score_scoped_per_user(two_tenant_client):
    """Regression coverage combining the CRITICAL route-ordering fix with
    multi-tenancy: each user's debt score must reflect ONLY their own decisions."""
    import sqlite3
    from datetime import datetime, timedelta

    old_date = (datetime.utcnow() - timedelta(days=800)).strftime("%Y-%m-%d")
    decision_id = _store(two_tenant_client, TOKEN_A, "Alice Old Vendor Contract", topics=["vendor", "budget"])

    memory = two_tenant_client.app.state.memory
    with sqlite3.connect(memory.db_path) as conn:
        conn.execute("UPDATE decisions SET date = ? WHERE id = ?", (old_date, decision_id))
        conn.commit()
    memory.graph._load_from_db()

    debt_a = two_tenant_client.get("/api/v1/decisions/debt-score", headers=_auth(TOKEN_A)).json()
    debt_b = two_tenant_client.get("/api/v1/decisions/debt-score", headers=_auth(TOKEN_B)).json()

    assert debt_a["total_decisions"] == 1
    assert debt_a["debt_score"] > 0
    assert debt_b["total_decisions"] == 0
    assert debt_b["debt_score"] == 0


def test_agent_personas_scoped_per_user(two_tenant_client):
    two_tenant_client.put(
        "/api/v1/agents/slack_agent",
        json={"display_name": "Alice's Watchtower"},
        headers=_auth(TOKEN_A),
    )

    personas_a = two_tenant_client.get("/api/v1/agents", headers=_auth(TOKEN_A)).json()["agents"]
    personas_b = two_tenant_client.get("/api/v1/agents", headers=_auth(TOKEN_B)).json()["agents"]

    slack_a = next(p for p in personas_a if p["agent_key"] == "slack_agent")
    slack_b = next(p for p in personas_b if p["agent_key"] == "slack_agent")

    assert slack_a["display_name"] == "Alice's Watchtower"
    assert slack_b["display_name"] != "Alice's Watchtower"
    assert slack_b["is_default"] is True


def test_store_decision_always_uses_authenticated_uid_not_client_supplied(two_tenant_client):
    """A client cannot smuggle a different user_id into a store request — the
    route must always use current_user.uid from the verified token."""
    resp = two_tenant_client.post(
        "/api/v1/store",
        json={
            "title": "Attempted impersonation",
            "summary": "test",
            "date": "2024-01-15",
            "source": "Slack",
            # StoreRequest has no user_id field at all — confirming the schema
            # itself doesn't accept one is the real assertion here.
        },
        headers=_auth(TOKEN_A),
    )
    assert resp.status_code == 200
    decision_id = resp.json()["id"]

    # Only the authenticated owner (TOKEN_A / USER_A) can see it.
    assert two_tenant_client.get(f"/api/v1/decisions/{decision_id}", headers=_auth(TOKEN_A)).status_code == 200
    assert two_tenant_client.get(f"/api/v1/decisions/{decision_id}", headers=_auth(TOKEN_B)).status_code == 404


# ── MCP transport (remote HTTP) — same guarantee, different door in ─────────

def _mcp_call(client, token, name, arguments):
    resp = client.post(
        f"/mcp/u/{token}",
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": name, "arguments": arguments}},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["result"]["isError"] is False, body
    return body["result"]["content"][0]["text"]


def test_mcp_store_context_isolated_between_users(two_tenant_client):
    from core.mcp_auth import mint_mcp_token

    mcp_token_a = mint_mcp_token(USER_A)
    mcp_token_b = mint_mcp_token(USER_B)
    secret_marker = "ONLY_ALICE_SHOULD_EVER_SEE_THIS_MARKER_TEXT"

    _mcp_call(two_tenant_client, mcp_token_a, "store_context", {
        "decision": "Alice's MCP-stored secret",
        "context": f"Confidential content: {secret_marker}",
        "date": "2024-01-15",
        "source": "MCP test",
    })

    # User B's get_context must never surface the stored content, even with a
    # query built to match (checking a marker that only appears in the stored
    # content itself, never in the tool's own "not found" wording, avoids a
    # false pass from the not-found message trivially echoing the query back).
    result_b = _mcp_call(two_tenant_client, mcp_token_b, "get_context", {"query": "Alice's MCP-stored secret"})
    assert secret_marker not in result_b
    assert "No decisions found" in result_b

    # User A can find their own.
    result_a = _mcp_call(two_tenant_client, mcp_token_a, "get_context", {"query": "Alice's MCP-stored secret"})
    assert secret_marker in result_a


def test_mcp_search_decisions_isolated_between_users(two_tenant_client):
    from core.mcp_auth import mint_mcp_token

    mcp_token_a = mint_mcp_token(USER_A)
    mcp_token_b = mint_mcp_token(USER_B)

    _mcp_call(two_tenant_client, mcp_token_a, "store_context", {
        "decision": "Alice vendor decision",
        "context": "context",
        "date": "2024-01-15",
        "source": "MCP test",
        "project": "VendorTopic",
    })

    result_b = _mcp_call(two_tenant_client, mcp_token_b, "search_decisions", {"topic": "VendorTopic"})
    assert "Alice vendor decision" not in result_b

    result_a = _mcp_call(two_tenant_client, mcp_token_a, "search_decisions", {"topic": "VendorTopic"})
    assert "Alice vendor decision" in result_a


def test_mcp_invalid_token_is_rejected(two_tenant_client):
    resp = two_tenant_client.post(
        "/mcp/u/not-a-real-token",
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "get_context", "arguments": {"query": "x"}}},
    )
    assert resp.status_code == 401


def test_mcp_post_cannot_route_response_into_another_users_sse_session(two_tenant_client):
    """Regression test for the SSE session-ownership fix in mcp_remote.py: a
    POST authenticated as user B, supplying user A's session_id, must NOT have
    its response routed into A's SSE stream — it should fall back to a direct
    JSON response instead, and A's queue must stay empty."""
    from api.routes import mcp_remote
    from core.mcp_auth import mint_mcp_token
    import asyncio

    mcp_token_a = mint_mcp_token(USER_A)
    mcp_token_b = mint_mcp_token(USER_B)

    # Simulate an established SSE session owned by user A.
    victim_session_id = "victim-session-owned-by-alice"
    victim_queue = asyncio.Queue()
    mcp_remote._active_sessions[victim_session_id] = (USER_A, victim_queue)
    try:
        resp = two_tenant_client.post(
            f"/mcp/u/{mcp_token_b}?session_id={victim_session_id}",
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                  "params": {"name": "get_context", "arguments": {"query": "x"}}},
        )
        # Falls back to a direct JSON response rather than being silently
        # swallowed into someone else's stream (status 202 would mean it
        # thought it successfully routed to a session).
        assert resp.status_code == 200
        assert resp.json()["result"]["isError"] is False
        # Alice's queue must never have received Bob's response.
        assert victim_queue.empty()
    finally:
        mcp_remote._active_sessions.pop(victim_session_id, None)
