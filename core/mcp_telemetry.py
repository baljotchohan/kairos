"""
Real MCP tool-call telemetry — persists every tool invocation (both
transports) to SQLite so the dashboard's "MCP Activity Monitor" panel can
show actual call history instead of a hardcoded/simulated log. Previously
neither transport recorded invocations anywhere queryable (only failures hit
stdlib logging), so there was no data to wire the panel to at all.

Fail-safe by design: a telemetry write/read failure must never break an
actual MCP tool call or an admin page load — every function here swallows
its own exceptions and degrades to a no-op / empty result.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime

from config import config

# Tools that mutate state, for the read/write split shown in the dashboard.
WRITE_TOOLS = {"store_context", "trigger_ingestion"}


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(config.SQLITE_PATH, timeout=30.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=30000;")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS mcp_call_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     TEXT NOT NULL,
            tool_name   TEXT NOT NULL,
            transport   TEXT NOT NULL,
            client_name TEXT,
            detail      TEXT,
            status      TEXT NOT NULL,
            created_at  TEXT NOT NULL
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_mcp_call_log_user ON mcp_call_log(user_id, created_at DESC)")
    return conn


def log_tool_call(
    user_id: str,
    tool_name: str,
    transport: str,
    client_name: str = "",
    detail: str = "",
    status: str = "success",
) -> None:
    """Record one tool invocation. Never raises — a telemetry failure must
    never take down (or even slow down the caller's error path of) an
    actual MCP tool call."""
    if not user_id:
        return
    conn = None
    try:
        conn = _connect()
        conn.execute(
            "INSERT INTO mcp_call_log (user_id, tool_name, transport, client_name, detail, status, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (user_id, tool_name, transport, client_name, (detail or "")[:300], status, datetime.utcnow().isoformat()),
        )
        conn.commit()
        # Keep only the most recent 500 rows per user — this is a live
        # activity feed, not an audit log; unbounded growth serves no purpose.
        conn.execute(
            "DELETE FROM mcp_call_log WHERE user_id = ? AND id NOT IN ("
            "  SELECT id FROM mcp_call_log WHERE user_id = ? ORDER BY id DESC LIMIT 500"
            ")",
            (user_id, user_id),
        )
        conn.commit()
    except Exception as e:
        print(f"[MCPTelemetry] log_tool_call error: {e}")
    finally:
        if conn is not None:
            conn.close()


def get_recent_calls(user_id: str, limit: int = 20) -> list[dict]:
    """Most recent tool calls for this user, newest first."""
    if not user_id:
        return []
    conn = None
    try:
        conn = _connect()
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT id, tool_name, transport, client_name, detail, status, created_at "
            "FROM mcp_call_log WHERE user_id = ? ORDER BY id DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]
    except Exception as e:
        print(f"[MCPTelemetry] get_recent_calls error: {e}")
        return []
    finally:
        if conn is not None:
            conn.close()


def get_stats(user_id: str) -> dict:
    """Aggregate counters for this user: total requests, read vs write op
    split, and count of distinct clients seen — real numbers derived from
    mcp_call_log, not a fixed placeholder."""
    empty = {"total_requests": 0, "read_ops": 0, "write_ops": 0, "active_clients": 0}
    if not user_id:
        return empty
    conn = None
    try:
        conn = _connect()
        total = conn.execute("SELECT COUNT(*) FROM mcp_call_log WHERE user_id = ?", (user_id,)).fetchone()[0]
        write_placeholders = ",".join("?" * len(WRITE_TOOLS))
        write_ops = conn.execute(
            f"SELECT COUNT(*) FROM mcp_call_log WHERE user_id = ? AND tool_name IN ({write_placeholders})",
            (user_id, *WRITE_TOOLS),
        ).fetchone()[0]
        active_clients = conn.execute(
            "SELECT COUNT(DISTINCT client_name) FROM mcp_call_log WHERE user_id = ? AND client_name != ''",
            (user_id,),
        ).fetchone()[0]
        return {
            "total_requests": total,
            "read_ops": total - write_ops,
            "write_ops": write_ops,
            "active_clients": active_clients,
        }
    except Exception as e:
        print(f"[MCPTelemetry] get_stats error: {e}")
        return empty
    finally:
        if conn is not None:
            conn.close()
