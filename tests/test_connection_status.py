"""
Regression tests for the connection-status fast path in the orchestrator.

"Which apps am I connected to?" is a factual system-state question. It must be
answered directly from the real token store, never by an LLM that could route it
to the greeting path and invent a connected-apps list. These tests lock in:
  1. The detector fires only on genuine status questions (no false positives on
     decision questions that merely contain the word "connect").
  2. The answer builder reflects the real token store, including treating a
     disconnected row as not-connected.
"""

import core.orchestrator as orch
import api.routes.oauth as oauth


# ── Detector ──────────────────────────────────────────────────────────────────

def test_detector_true_on_status_questions():
    for q in [
        "which apps are connected",
        "what tools am I connected to",
        "am I connected to anything",
        "is anything connected",
        "what's connected",
        "list my connected integrations",
        "show connected sources",
        "what accounts do I have connected",
    ]:
        assert orch._is_connection_status_question(q) is True, q


def test_detector_false_on_decision_and_action_questions():
    # These contain "connect" or app-words but are NOT status questions — the
    # detector must not hijack them away from the real answering pipeline.
    for q in [
        "why did we decide to connect our CRM to Salesforce in 2019",
        "connect my slack",
        "why do we use AWS",
        "how many unread emails do I have",
        "what are my open PRs",
        "who approved the vendor contract",
        "what is kairos",
    ]:
        assert orch._is_connection_status_question(q) is False, q


# ── Answer builder ────────────────────────────────────────────────────────────

def test_answer_when_nothing_connected(monkeypatch):
    monkeypatch.setattr(oauth, "_get_token", lambda uid, svc: None)
    answer = orch._build_connection_status_answer("u1")
    assert "not connected to any apps yet" in answer.lower()
    # every connectable source is offered
    for name in ["Slack", "Gmail", "Google Drive", "Notion", "Jira", "Zoom", "GitHub"]:
        assert name in answer


def test_answer_reflects_connected_sources(monkeypatch):
    # Slack + the shared Google grant connected → Gmail AND Drive both show.
    monkeypatch.setattr(
        oauth, "_get_token",
        lambda uid, svc: {"connected_at": "x"} if svc in ("slack", "google") else None,
    )
    answer = orch._build_connection_status_answer("u1")
    assert "connected to 3 sources" in answer.lower()
    assert "Slack" in answer and "Gmail" in answer and "Google Drive" in answer
    assert "## ⚪ Not connected yet" in answer


def test_live_source_reroute_fires_on_named_tool_requests():
    # Naming a connected tool + a retrieval verb must be recognized as a
    # live-data request so the orchestrator reroutes it away from the memory
    # search path (where it died with "I wasn't able to generate a response").
    for q in [
        "ok so use notion list all data in kairos",
        "list all data in notion",
        "list all my notion pages",
        "show me everything in notion",
        "list my github repos",
        "what are my open PRs",
        "give me all my drive files",
        "how many jira tickets do I have",
    ]:
        assert orch._looks_like_live_source_request(q) is True, q


def test_live_source_reroute_ignores_decision_and_generic_questions():
    # Decision/history questions that merely mention a tool must NOT be
    # rerouted — they belong in the memory-search path.
    for q in [
        "why did we decide to use slack",
        "why do we use notion over confluence",
        "what was the reason we chose github",
        "why do we use React",
        "who approved the vendor contract",
        "summarize our q3 vendor decisions",
    ]:
        assert orch._looks_like_live_source_request(q) is False, q


def test_disconnected_row_counts_as_not_connected(monkeypatch):
    def fake(uid, svc):
        if svc == "slack":
            return {"disconnected": True}
        if svc == "github":
            return {"connected_at": "x"}
        return None
    monkeypatch.setattr(oauth, "_get_token", fake)
    answer = orch._build_connection_status_answer("u1")
    assert "connected to 1 source" in answer.lower()
    # Slack's disconnected row must land it in the "not connected" list.
    connected_section = answer.split("## ⚪")[0]
    assert "Slack" not in connected_section
    assert "GitHub" in connected_section
