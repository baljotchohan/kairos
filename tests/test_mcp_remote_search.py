"""Tests for api/routes/mcp_remote.py's search_decisions(project=...) filter.

DecisionNode has no `project` field — store_context() saves it as a topic
(topics=[project]). The remote MCP transport used to filter on
`getattr(node, "project", None)`, which always returned None, so `project`
silently matched nothing while the stdio transport (mcp_server.py) handled
the identical parameter correctly via topic-based search — a transport
behavioral drift on a documented, advertised tool parameter."""

from unittest.mock import patch

import pytest

from core.memory import KairosMemory
from core.graph import DecisionNode
from api.routes.mcp_remote import _tool_search_decisions

TEST_UID = "testuser"


@pytest.fixture
def memory(tmp_path):
    with patch("core.memory.FireworksEmbeddingFunction") as mock_ef:
        from chromadb.utils import embedding_functions
        mock_ef.return_value = embedding_functions.DefaultEmbeddingFunction()
        mem = KairosMemory(
            chroma_path=str(tmp_path / "chroma"),
            db_path=str(tmp_path / "test.db"),
            obsidian_vault=str(tmp_path / "vault"),
        )
    return mem


def _store(memory, title, project, topics=None):
    node = DecisionNode(
        id=f"n-{title}", title=title, summary=f"Summary for {title}", date="2026-03-01",
        participants=["Alice"], source="slack", source_url="https://x",
        topics=(topics or []) + ([project] if project else []),
        outcome="approved", raw_text="", metadata={"project": project or ""}, user_id=TEST_UID,
    )
    memory.store(node, user_id=TEST_UID)
    return node


def test_project_filter_finds_matching_decision(memory):
    _store(memory, "Ship mobile beta", project="Mobile")

    result = _tool_search_decisions(memory, user_id=TEST_UID, project="Mobile")

    assert "Ship mobile beta" in result
    assert "No decisions found" not in result


def test_project_filter_excludes_non_matching_decision(memory):
    _store(memory, "Ship mobile beta", project="Mobile")
    _store(memory, "Renew vendor contract", project="Infrastructure")

    result = _tool_search_decisions(memory, user_id=TEST_UID, project="Infrastructure")

    assert "Renew vendor contract" in result
    assert "Ship mobile beta" not in result


def test_project_and_topic_together_merge_results(memory):
    """When both topic and project are given, topic takes priority but
    project results are still merged in (deduplicated) — mirrors the stdio
    transport's behavior exactly."""
    _store(memory, "Ship mobile beta", project="Mobile", topics=["AWS"])
    _store(memory, "Unrelated AWS cleanup", project="Backend", topics=["AWS"])

    result = _tool_search_decisions(memory, user_id=TEST_UID, topic="AWS", project="Mobile")

    assert "Ship mobile beta" in result
    assert "Unrelated AWS cleanup" in result


def test_no_filters_returns_a_helpful_message_not_everything(memory):
    _store(memory, "Ship mobile beta", project="Mobile")

    result = _tool_search_decisions(memory, user_id=TEST_UID)

    assert "provide at least one search filter" in result.lower()
