"""Tests for core/decision_intelligence.py — proactive analysis on top of memory.py/graph.py.

LLM calls (core.decision_intelligence.fireworks.complete) are mocked throughout —
these tests exercise the deterministic retrieval/scoring logic, not the model.
"""

import json
from datetime import datetime, timedelta
from unittest.mock import patch, AsyncMock

import pytest

from core.graph import DecisionNode
from core.memory import KairosMemory
from core import decision_intelligence as di

TEST_UID = "testuser"


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def memory(tmp_path):
    """KairosMemory with temp paths and mocked Fireworks embeddings (matches test_memory.py)."""
    chroma_path = str(tmp_path / "chroma")
    db_path = str(tmp_path / "test.db")
    vault_path = str(tmp_path / "vault")

    with patch("core.memory.FireworksEmbeddingFunction") as mock_ef:
        from chromadb.utils import embedding_functions
        mock_ef.return_value = embedding_functions.DefaultEmbeddingFunction()
        mem = KairosMemory(chroma_path=chroma_path, db_path=db_path, obsidian_vault=vault_path)
    return mem


def make_node(id, title, date="2024-01-15", topics=None, outcome="", metadata=None, participants=None) -> DecisionNode:
    return DecisionNode(
        id=id, title=title, summary=f"{title} summary", date=date,
        participants=participants or ["Alice"], source="Slack #test", source_url="https://x/1",
        topics=topics or ["Engineering"], outcome=outcome or "Positive outcome.",
        metadata=metadata or {},
    )


def _old_date(days_ago: int) -> str:
    return (datetime.utcnow() - timedelta(days=days_ago)).strftime("%Y-%m-%d")


# ── compute_debt_score (pure SQL/graph, no LLM) ────────────────────────────────

def test_debt_score_empty_is_zero(memory):
    result = di.compute_debt_score(memory, TEST_UID)
    assert result == {"debt_score": 0, "high_risk_count": 0, "total_decisions": 0, "top_offenders": []}


def test_debt_score_fails_closed_without_user_id(memory):
    memory.store(make_node("v1", "Old vendor contract", date=_old_date(800), topics=["vendor"]), user_id=TEST_UID)
    result = di.compute_debt_score(memory, None)
    assert result["total_decisions"] == 0


def test_debt_score_flags_stale_high_impact_decision(memory):
    memory.store(make_node("v1", "Old vendor contract renewal", date=_old_date(800), topics=["vendor", "budget"]), user_id=TEST_UID)
    memory.store(make_node("v2", "Recent decision", date=_old_date(5), topics=["engineering"]), user_id=TEST_UID)

    result = di.compute_debt_score(memory, TEST_UID)
    assert result["total_decisions"] == 2
    assert result["debt_score"] > 0
    assert result["high_risk_count"] == 1
    assert "v1" in result["top_offenders"]
    assert "v2" not in result["top_offenders"]


def test_debt_score_excludes_decisions_with_follow_up(memory):
    memory.store(make_node("v1", "Old vendor contract", date=_old_date(800), topics=["vendor"]), user_id=TEST_UID)
    memory.store(make_node("v2", "Review of vendor contract", date=_old_date(10), topics=["vendor"]), user_id=TEST_UID)
    memory.graph.add_relation("v2", "v1", "follow_up")

    result = di.compute_debt_score(memory, TEST_UID)
    assert "v1" not in result["top_offenders"]


# ── DecisionGraph.get_edges_by_type ────────────────────────────────────────────

def test_get_edges_by_type_same_topic(memory):
    memory.store(make_node("a1", "First AWS Decision", topics=["AWS", "Infra"]), user_id=TEST_UID)
    memory.store(make_node("a2", "Second AWS Decision", topics=["AWS"]), user_id=TEST_UID)

    pairs = memory.graph.get_edges_by_type("same_topic", user_id=TEST_UID)
    ids = {(a.id, b.id) for a, b in pairs}
    assert ("a2", "a1") in ids or ("a1", "a2") in ids


def test_get_edges_by_type_scopes_to_user(memory):
    memory.store(make_node("a1", "User A Decision", topics=["Shared"]), user_id="user-a")
    memory.store(make_node("a2", "User B Decision", topics=["Shared"]), user_id="user-b")

    pairs = memory.graph.get_edges_by_type("same_topic", user_id="user-a")
    assert pairs == []


# ── find_similar_decisions (mocked LLM) ────────────────────────────────────────

@pytest.mark.asyncio
async def test_find_similar_decisions_no_candidates(memory):
    result = await di.find_similar_decisions(memory, TEST_UID, "anything")
    assert result["matches"] == []


@pytest.mark.asyncio
async def test_find_similar_decisions_fails_closed_without_user_id(memory):
    result = await di.find_similar_decisions(memory, None, "anything")
    assert result["matches"] == []


@pytest.mark.asyncio
async def test_find_similar_decisions_filters_via_llm(memory):
    node = make_node("m1", "Failed mobile app attempt", topics=["mobile"], outcome="Failed, no expertise")
    memory.store(node, user_id=TEST_UID)

    with patch.object(memory, "semantic_search", return_value=[node]), \
         patch("core.decision_intelligence.fireworks.complete", new=AsyncMock(
             return_value=json.dumps({
                 "relevant_indices": [0],
                 "verdict": "Yes — tried in 2021, failed due to no mobile expertise.",
             })
         )):
        result = await di.find_similar_decisions(memory, TEST_UID, "should we build a mobile app", limit=5)

    assert len(result["matches"]) == 1
    assert result["matches"][0]["decision_id"] == "m1"
    assert "expertise" in result["verdict"].lower()


# ── detect_decision_patterns (mocked LLM) ──────────────────────────────────────

@pytest.mark.asyncio
async def test_detect_decision_patterns_stale_vendor(memory):
    memory.store(make_node("v1", "Vendor contract signed", date=_old_date(500), topics=["vendor"], outcome="Signed"), user_id=TEST_UID)

    with patch("core.decision_intelligence.fireworks.complete", new=AsyncMock(
        return_value=json.dumps([{"description": "Vendor contract unreviewed.", "recommendation": "Review it."}])
    )):
        result = await di.detect_decision_patterns(memory, TEST_UID, lookback_days=100000)

    assert len(result["patterns"]) == 1
    assert result["patterns"][0]["pattern_type"] == "unreviewed_vendor_spend"
    assert "v1" in result["patterns"][0]["affected_decisions"]


@pytest.mark.asyncio
async def test_detect_decision_patterns_empty_when_nothing_flagged(memory):
    memory.store(make_node("e1", "Recent normal decision", date=_old_date(5)), user_id=TEST_UID)
    result = await di.detect_decision_patterns(memory, TEST_UID)
    assert result["patterns"] == []


@pytest.mark.asyncio
async def test_detect_decision_patterns_fails_closed_without_user_id(memory):
    result = await di.detect_decision_patterns(memory, None)
    assert result["patterns"] == []


# ── predict_decision_risk (mocked LLM) ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_predict_decision_risk_scores_stale_decision(memory):
    memory.store(make_node("r1", "Old budget decision", date=_old_date(800), topics=["budget"]), user_id=TEST_UID)

    with patch("core.decision_intelligence.fireworks.complete", new=AsyncMock(
        return_value=json.dumps([{"recommendation": "Reassign an owner."}])
    )):
        result = await di.predict_decision_risk(memory, TEST_UID)

    assert len(result["at_risk"]) == 1
    assert result["at_risk"][0]["decision_id"] == "r1"
    assert result["at_risk"][0]["risk_score"] > 0


@pytest.mark.asyncio
async def test_predict_decision_risk_fails_closed_without_user_id(memory):
    result = await di.predict_decision_risk(memory, None)
    assert result["at_risk"] == []
