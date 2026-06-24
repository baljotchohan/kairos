"""Tests for core/memory.py — ChromaDB + SQLite + graph layer."""

import os
import pytest
from unittest.mock import patch, MagicMock

from core.graph import DecisionNode, DecisionGraph
from core.memory import KairosMemory


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def memory(tmp_path):
    """KairosMemory with temp paths and mocked Fireworks embeddings."""
    chroma_path = str(tmp_path / "chroma")
    db_path = str(tmp_path / "test.db")
    vault_path = str(tmp_path / "vault")

    # Patch the Fireworks embedding function so no API key is needed
    with patch("core.memory.FireworksEmbeddingFunction") as mock_ef:
        from chromadb.utils import embedding_functions
        mock_ef.return_value = embedding_functions.DefaultEmbeddingFunction()
        mem = KairosMemory(
            chroma_path=chroma_path,
            db_path=db_path,
            obsidian_vault=vault_path,
        )
    return mem


def make_node(id="n1", title="Test Decision", topics=None, participants=None) -> DecisionNode:
    return DecisionNode(
        id=id,
        title=title,
        summary="A test decision was made.",
        date="2024-01-15",
        participants=participants or ["Alice", "Bob"],
        source="Slack #test",
        source_url="https://slack.example.com/archives/C1/p1",
        topics=topics or ["Engineering"],
        outcome="The outcome was positive.",
    )


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_store_and_retrieve(memory):
    node = make_node(id="test-1", title="Chose PostgreSQL over MongoDB")
    memory.store(node)

    results = memory.semantic_search("database choice", n_results=5)
    assert len(results) >= 1
    titles = [r.title for r in results]
    assert "Chose PostgreSQL over MongoDB" in titles


def test_structured_search_by_topic(memory):
    memory.store(make_node(id="s1", title="Infrastructure Decision", topics=["Infrastructure"]))
    memory.store(make_node(id="s2", title="Product Decision", topics=["Product"]))

    infra = memory.structured_search(topic="Infrastructure")
    assert any(n.id == "s1" for n in infra)
    assert all(n.id != "s2" for n in infra)


def test_structured_search_by_person(memory):
    memory.store(make_node(id="p1", title="John's Call", participants=["John Smith", "Alice"]))
    memory.store(make_node(id="p2", title="Bob's Call", participants=["Bob Jones"]))

    results = memory.structured_search(person="John")
    ids = [n.id for n in results]
    assert "p1" in ids
    assert "p2" not in ids


def test_structured_search_date_range(memory):
    memory.store(make_node(id="d1", title="Early Decision"))
    # Manually set date in SQLite
    import sqlite3, json
    with sqlite3.connect(memory.db_path) as conn:
        conn.execute("UPDATE decisions SET date = '2020-03-01' WHERE id = 'd1'")
        conn.commit()

    results = memory.structured_search(date_from="2020-01-01", date_to="2020-12-31")
    ids = [n.id for n in results]
    assert "d1" in ids


def test_graph_auto_links(memory):
    memory.store(make_node(id="g1", title="First AWS Decision", topics=["Infrastructure", "AWS"]))
    memory.store(make_node(id="g2", title="Second AWS Decision", topics=["Infrastructure", "Cloud"]))

    connected = memory.graph.get_connected("g1", depth=1)
    connected_ids = [n.id for n in connected]
    assert "g2" in connected_ids


def test_obsidian_export_creates_files(memory):
    import os
    memory.store(make_node(id="obs1", title="My Special Decision"))
    memory.rebuild_obsidian()

    vault_files = []
    for root, dirs, files in os.walk(memory.obsidian_vault):
        vault_files.extend(files)

    md_files = [f for f in vault_files if f.endswith(".md")]
    assert len(md_files) >= 1


def test_hybrid_search_returns_results(memory):
    memory.store(make_node(id="h1", title="React over Vue Decision", topics=["Frontend"]))
    memory.store(make_node(id="h2", title="Node.js over Python", topics=["Backend", "Engineering"]))

    results = memory.hybrid_search("frontend framework choice", n_results=5)
    assert len(results) >= 1


def test_get_context_mcp_format(memory):
    memory.store(make_node(id="mc1", title="Vendor Contract Decision", topics=["Finance"]))

    ctx = memory.get_context("vendor contract", n_results=5)
    assert isinstance(ctx, list)
    if ctx:
        assert "id" in ctx[0]
        assert "title" in ctx[0]
        assert "summary" in ctx[0]
        assert "outcome" in ctx[0]
