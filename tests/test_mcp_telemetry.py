"""Tests for core/mcp_telemetry.py — real MCP tool-call logging.

Previously neither MCP transport persisted tool invocations anywhere
queryable (only failures hit stdlib logging), so the dashboard's "Activity
Monitor" panel had no real data to show and rendered a hardcoded/simulated
log instead. This module is the actual telemetry store both transports
write to."""

from unittest.mock import patch

import pytest

from config import config
from core.mcp_telemetry import log_tool_call, get_recent_calls, get_stats, WRITE_TOOLS


@pytest.fixture(autouse=True)
def _isolated_sqlite(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "SQLITE_PATH", str(tmp_path / "telemetry_test.db"))
    yield


def test_log_and_retrieve_a_call():
    log_tool_call("user-a", "get_context", transport="stdio", client_name="Claude Desktop", status="success")

    calls = get_recent_calls("user-a")

    assert len(calls) == 1
    assert calls[0]["tool_name"] == "get_context"
    assert calls[0]["transport"] == "stdio"
    assert calls[0]["client_name"] == "Claude Desktop"
    assert calls[0]["status"] == "success"


def test_calls_are_scoped_per_user():
    log_tool_call("user-a", "get_context", transport="stdio", status="success")
    log_tool_call("user-b", "store_context", transport="remote", status="success")

    calls_a = get_recent_calls("user-a")
    calls_b = get_recent_calls("user-b")

    assert len(calls_a) == 1 and calls_a[0]["tool_name"] == "get_context"
    assert len(calls_b) == 1 and calls_b[0]["tool_name"] == "store_context"


def test_recent_calls_newest_first():
    log_tool_call("user-a", "get_context", transport="stdio", status="success")
    log_tool_call("user-a", "search_decisions", transport="stdio", status="success")

    calls = get_recent_calls("user-a")

    assert calls[0]["tool_name"] == "search_decisions"
    assert calls[1]["tool_name"] == "get_context"


def test_stats_splits_read_and_write_ops():
    log_tool_call("user-a", "get_context", transport="stdio", status="success")
    log_tool_call("user-a", "search_decisions", transport="stdio", status="success")
    log_tool_call("user-a", "store_context", transport="stdio", status="success")
    log_tool_call("user-a", "trigger_ingestion", transport="remote", status="success")

    stats = get_stats("user-a")

    assert stats["total_requests"] == 4
    assert stats["write_ops"] == 2  # store_context + trigger_ingestion
    assert stats["read_ops"] == 2


def test_stats_counts_distinct_clients():
    log_tool_call("user-a", "get_context", transport="stdio", client_name="Claude Desktop", status="success")
    log_tool_call("user-a", "get_context", transport="remote", client_name="ChatGPT", status="success")
    log_tool_call("user-a", "get_context", transport="remote", client_name="ChatGPT", status="success")

    stats = get_stats("user-a")

    assert stats["active_clients"] == 2


def test_log_tool_call_is_a_safe_no_op_without_user_id():
    log_tool_call("", "get_context", transport="stdio", status="success")
    log_tool_call(None, "get_context", transport="stdio", status="success")
    # Must not raise, and must not create any orphaned rows readable by anyone
    assert get_recent_calls("") == []


def test_get_functions_fail_safe_on_db_error_never_raise():
    """Telemetry must never break an admin page load or a real MCP tool call
    just because logging itself hit a problem."""
    with patch("core.mcp_telemetry._connect", side_effect=Exception("db exploded")):
        assert get_recent_calls("user-a") == []
        assert get_stats("user-a") == {"total_requests": 0, "read_ops": 0, "write_ops": 0, "active_clients": 0}
        log_tool_call("user-a", "get_context", transport="stdio", status="success")  # must not raise


def test_write_tools_set_matches_the_tools_that_actually_mutate_state():
    assert WRITE_TOOLS == {"store_context", "trigger_ingestion"}
