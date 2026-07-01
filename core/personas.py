"""
KAIROS Agent Personas — per-user display names + tone presets for the
internal agents. Purely a presentation layer: agent_key (e.g. "slack_agent")
is the fixed internal identifier used everywhere in code/traces; display_name
and tone_preset only affect user-facing labels and the framing of an agent's
own generated text (never its extraction/classification logic).
"""

from __future__ import annotations

import time
import sqlite3
import contextlib
from typing import Optional

TONE_PRESETS = ("professional", "concise", "analyst", "custom")

# Internal agent_key -> (display group, default display name)
DEFAULT_PERSONAS: dict[str, dict] = {
    "slack_agent":     {"display_name": "Slack Extraction Agent",  "group": "Extraction Agents"},
    "email_agent":     {"display_name": "Email Extraction Agent",  "group": "Extraction Agents"},
    "drive_agent":     {"display_name": "Drive Extraction Agent",  "group": "Extraction Agents"},
    "notion_agent":    {"display_name": "Notion Extraction Agent", "group": "Extraction Agents"},
    "meeting_agent":   {"display_name": "Meeting Extraction Agent","group": "Extraction Agents"},
    "synthesis_agent": {"display_name": "Synthesis Engine",        "group": "Reasoning"},
    "intent_agent":    {"display_name": "Router",                  "group": "Reasoning"},
    "context_agent":   {"display_name": "Retrieval Engine",        "group": "Reasoning"},
    "live_data_agent": {"display_name": "Live Agent",              "group": "Reasoning"},
    "research_agent":  {"display_name": "Deep Research Agent",     "group": "Reasoning"},
}


def default_persona(agent_key: str) -> dict:
    d = DEFAULT_PERSONAS.get(agent_key, {"display_name": agent_key, "group": "Other"})
    return {
        "agent_key": agent_key,
        "display_name": d["display_name"],
        "group": d["group"],
        "tone_preset": "professional",
        "is_default": True,
    }


class AgentPersonaStore:
    """Per-user overrides of agent display name + tone, stored in the shared SQLite file."""

    def __init__(self, db_path: str = None):
        from config import config
        self.db_path = db_path or config.SQLITE_PATH
        self._init_table()

    @contextlib.contextmanager
    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA busy_timeout=30000;")
        try:
            yield conn
        finally:
            conn.close()

    def _init_table(self):
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS agent_personas (
                    user_id      TEXT NOT NULL,
                    agent_key    TEXT NOT NULL,
                    display_name TEXT NOT NULL,
                    tone_preset  TEXT NOT NULL DEFAULT 'professional',
                    created_at   REAL,
                    updated_at   REAL,
                    PRIMARY KEY (user_id, agent_key)
                )
            """)
            conn.commit()

    def list_for_user(self, user_id: str) -> list[dict]:
        """All known agent_keys with either the user's override or the default."""
        if not user_id:
            return [default_persona(k) for k in DEFAULT_PERSONAS]
        overrides: dict[str, tuple] = {}
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT agent_key, display_name, tone_preset FROM agent_personas WHERE user_id = ?",
                (user_id,),
            ).fetchall()
            overrides = {r[0]: (r[1], r[2]) for r in rows}

        result = []
        for agent_key, d in DEFAULT_PERSONAS.items():
            if agent_key in overrides:
                display_name, tone_preset = overrides[agent_key]
                result.append({
                    "agent_key": agent_key,
                    "display_name": display_name,
                    "group": d["group"],
                    "tone_preset": tone_preset,
                    "is_default": False,
                })
            else:
                result.append(default_persona(agent_key))
        return result

    def get(self, user_id: str, agent_key: str) -> dict:
        if not user_id:
            return default_persona(agent_key)
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT display_name, tone_preset FROM agent_personas WHERE user_id = ? AND agent_key = ?",
                (user_id, agent_key),
            ).fetchone()
        if not row:
            return default_persona(agent_key)
        return {
            "agent_key": agent_key,
            "display_name": row[0],
            "group": DEFAULT_PERSONAS.get(agent_key, {}).get("group", "Other"),
            "tone_preset": row[1],
            "is_default": False,
        }

    def upsert(self, user_id: str, agent_key: str, display_name: Optional[str] = None, tone_preset: Optional[str] = None) -> dict:
        if not user_id or agent_key not in DEFAULT_PERSONAS:
            raise ValueError("Unknown agent_key or missing user_id")
        if tone_preset and tone_preset not in TONE_PRESETS:
            raise ValueError(f"tone_preset must be one of {TONE_PRESETS}")

        current = self.get(user_id, agent_key)
        final_name = (display_name or current["display_name"]).strip()[:80]
        final_tone = tone_preset or current["tone_preset"]
        now = time.time()

        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO agent_personas (user_id, agent_key, display_name, tone_preset, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id, agent_key) DO UPDATE SET
                    display_name = excluded.display_name,
                    tone_preset = excluded.tone_preset,
                    updated_at = excluded.updated_at
            """, (user_id, agent_key, final_name, final_tone, now, now))
            conn.commit()

        return self.get(user_id, agent_key)

    def reset(self, user_id: str, agent_key: str):
        with self._get_connection() as conn:
            conn.execute(
                "DELETE FROM agent_personas WHERE user_id = ? AND agent_key = ?",
                (user_id, agent_key),
            )
            conn.commit()
        return default_persona(agent_key)
