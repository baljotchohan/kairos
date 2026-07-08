"""Tests for api/routes/admin.py's /admin/status connector metrics.

These used to be fabricated: last_synced was a single hardcoded date
regardless of when (or whether) that source ever actually synced, and
total_items was an arbitrary fraction of total_decisions rather than a real
per-source count. Both are now derived from the real inventory table."""

from unittest.mock import patch

import pytest

from core.memory import KairosMemory


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


def test_inventory_counts_reflects_real_per_source_totals(memory):
    memory.store_inventory("user-a", [
        {"source": "Slack", "item_id": "s1", "title": "msg 1", "date": "2026-01-01"},
        {"source": "Slack", "item_id": "s2", "title": "msg 2", "date": "2026-01-02"},
        {"source": "GitHub", "item_id": "g1", "title": "pr 1", "date": "2026-01-03"},
    ])

    counts = memory.inventory_counts("user-a")

    assert counts["Slack"] == 2
    assert counts["GitHub"] == 1
    assert "Jira" not in counts  # never synced — must not appear as a fabricated zero-with-data


def test_inventory_last_synced_reflects_real_fetch_time_not_a_placeholder(memory):
    memory.store_inventory("user-a", [
        {"source": "Slack", "item_id": "s1", "title": "msg 1", "date": "2026-01-01"},
    ])

    last_synced = memory.inventory_last_synced("user-a")

    assert "Slack" in last_synced
    # Real ISO timestamp from datetime.utcnow(), not the old hardcoded "2026-06-23T18:00:00Z"
    assert last_synced["Slack"] != "2026-06-23T18:00:00Z"
    assert last_synced["Slack"].startswith("20")  # sanity: looks like an ISO year


def test_inventory_counts_and_last_synced_are_scoped_per_user(memory):
    memory.store_inventory("user-a", [{"source": "Slack", "item_id": "s1", "title": "a", "date": "2026-01-01"}])
    memory.store_inventory("user-b", [
        {"source": "Slack", "item_id": "s2", "title": "b1", "date": "2026-01-01"},
        {"source": "Slack", "item_id": "s3", "title": "b2", "date": "2026-01-02"},
    ])

    assert memory.inventory_counts("user-a")["Slack"] == 1
    assert memory.inventory_counts("user-b")["Slack"] == 2


def test_inventory_counts_and_last_synced_fail_closed_without_user_id(memory):
    memory.store_inventory("user-a", [{"source": "Slack", "item_id": "s1", "title": "a", "date": "2026-01-01"}])

    assert memory.inventory_counts("") == {}
    assert memory.inventory_counts(None) == {}
    assert memory.inventory_last_synced("") == {}
    assert memory.inventory_last_synced(None) == {}
