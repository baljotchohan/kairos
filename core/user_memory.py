"""
KAIROS Per-User Memory Layer.

Provides persistent, per-user conversation history, profile learning,
and session management. Each user gets their own memory space so KAIROS
can personalize responses based on past interactions.

Architecture:
  - user_conversations: Every query + response stored per user_id
  - user_profiles: Learned preferences, frequent topics, role context
  - Sessions: Auto-grouped by 30-min idle gaps
"""

from __future__ import annotations

import json
import time
import uuid
import sqlite3
from typing import Optional
from dataclasses import dataclass, field, asdict


# ── Data Models ──────────────────────────────────────────────────────────────

@dataclass
class ConversationTurn:
    id: str
    user_id: str
    session_id: str
    role: str           # 'user' | 'assistant'
    content: str
    query_intent: str = ""
    timestamp: float = 0.0
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = time.time()


@dataclass
class UserProfile:
    user_id: str
    display_name: str = ""
    department: str = ""
    role_context: str = ""          # LLM-generated: "Engineering lead interested in infrastructure"
    frequent_topics: list[str] = field(default_factory=list)
    preferred_sources: list[str] = field(default_factory=list)
    interaction_summary: str = ""   # LLM-generated summary of user's history
    total_queries: int = 0
    last_active: float = 0.0
    created_at: float = 0.0
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        now = time.time()
        if not self.created_at:
            self.created_at = now
        if not self.last_active:
            self.last_active = now


# ── Session Boundary ─────────────────────────────────────────────────────────

SESSION_IDLE_GAP = 30 * 60  # 30 minutes — new session after this gap


# ── UserMemory Class ─────────────────────────────────────────────────────────

class UserMemory:
    """
    Per-user memory manager. Stores conversations, profiles, and sessions
    in SQLite alongside the main KAIROS database.
    """

    def __init__(self, db_path: str = None):
        from config import config
        self.db_path = db_path or config.SQLITE_PATH
        self._init_tables()

    # ── Schema ────────────────────────────────────────────────────────────────

    def _init_tables(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS user_conversations (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    query_intent TEXT DEFAULT '',
                    timestamp REAL NOT NULL,
                    metadata TEXT DEFAULT '{}'
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_conv_user
                ON user_conversations(user_id, timestamp DESC)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_conv_session
                ON user_conversations(session_id, timestamp ASC)
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS user_profiles (
                    user_id TEXT PRIMARY KEY,
                    display_name TEXT DEFAULT '',
                    department TEXT DEFAULT '',
                    role_context TEXT DEFAULT '',
                    frequent_topics TEXT DEFAULT '[]',
                    preferred_sources TEXT DEFAULT '[]',
                    interaction_summary TEXT DEFAULT '',
                    total_queries INTEGER DEFAULT 0,
                    last_active REAL,
                    created_at REAL,
                    metadata TEXT DEFAULT '{}'
                )
            """)
            conn.commit()

    # ── Store ─────────────────────────────────────────────────────────────────

    def store_message(
        self,
        user_id: str,
        session_id: str,
        role: str,
        content: str,
        query_intent: str = "",
        metadata: dict | None = None,
    ) -> ConversationTurn:
        """Store a single conversation turn."""
        turn = ConversationTurn(
            id=str(uuid.uuid4()),
            user_id=user_id,
            session_id=session_id,
            role=role,
            content=content,
            query_intent=query_intent,
            metadata=metadata or {},
        )
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO user_conversations
                (id, user_id, session_id, role, content, query_intent, timestamp, metadata)
                VALUES (?,?,?,?,?,?,?,?)
            """, (
                turn.id, turn.user_id, turn.session_id, turn.role,
                turn.content, turn.query_intent, turn.timestamp,
                json.dumps(turn.metadata),
            ))
            # Bump query count + last_active on user profile
            if role == "user":
                conn.execute("""
                    INSERT INTO user_profiles (user_id, total_queries, last_active, created_at)
                    VALUES (?, 1, ?, ?)
                    ON CONFLICT(user_id) DO UPDATE SET
                        total_queries = total_queries + 1,
                        last_active = ?
                """, (user_id, turn.timestamp, turn.timestamp, turn.timestamp))
            conn.commit()
        return turn

    # ── Read ──────────────────────────────────────────────────────────────────

    def get_session_history(
        self, user_id: str, session_id: str, limit: int = 50
    ) -> list[ConversationTurn]:
        """Get all messages in a specific session."""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute("""
                SELECT id, user_id, session_id, role, content, query_intent, timestamp, metadata
                FROM user_conversations
                WHERE user_id = ? AND session_id = ?
                ORDER BY timestamp ASC
                LIMIT ?
            """, (user_id, session_id, limit)).fetchall()
        return [self._row_to_turn(r) for r in rows]

    def get_recent_history(
        self, user_id: str, limit: int = 10
    ) -> list[ConversationTurn]:
        """Get most recent messages across all sessions."""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute("""
                SELECT id, user_id, session_id, role, content, query_intent, timestamp, metadata
                FROM user_conversations
                WHERE user_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
            """, (user_id, limit)).fetchall()
        return list(reversed([self._row_to_turn(r) for r in rows]))

    def get_current_session_context(
        self, user_id: str, max_turns: int = 6
    ) -> list[dict]:
        """
        Get the current session's recent turns as LLM-ready message dicts.
        Used to inject conversational context into the synthesis agent prompt.
        """
        session_id = self.get_or_create_session(user_id)
        turns = self.get_session_history(user_id, session_id, limit=max_turns)
        return [
            {"role": t.role, "content": t.content}
            for t in turns
        ]

    def list_sessions(self, user_id: str, limit: int = 20) -> list[dict]:
        """List all sessions for a user with preview info."""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute("""
                SELECT session_id,
                       MIN(timestamp) as started,
                       MAX(timestamp) as last_msg,
                       COUNT(*) as msg_count,
                       MIN(CASE WHEN role='user' THEN content END) as first_query
                FROM user_conversations
                WHERE user_id = ?
                GROUP BY session_id
                ORDER BY last_msg DESC
                LIMIT ?
            """, (user_id, limit)).fetchall()

        return [
            {
                "session_id": r[0],
                "started": r[1],
                "last_message": r[2],
                "message_count": r[3],
                "preview": (r[4] or "")[:100],
            }
            for r in rows
        ]

    def delete_session(self, user_id: str, session_id: str) -> int:
        """Delete all messages in a session. Returns count deleted."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                DELETE FROM user_conversations
                WHERE user_id = ? AND session_id = ?
            """, (user_id, session_id))
            conn.commit()
            return cursor.rowcount

    # ── Session Management ────────────────────────────────────────────────────

    def get_or_create_session(self, user_id: str) -> str:
        """
        Get the current active session or create a new one.
        A new session starts if the last message was > SESSION_IDLE_GAP ago.
        """
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute("""
                SELECT session_id, timestamp
                FROM user_conversations
                WHERE user_id = ?
                ORDER BY timestamp DESC
                LIMIT 1
            """, (user_id,)).fetchone()

        if row:
            last_session_id, last_timestamp = row
            if time.time() - last_timestamp < SESSION_IDLE_GAP:
                return last_session_id

        # Create new session
        return f"session-{uuid.uuid4().hex[:12]}"

    # ── User Profile ──────────────────────────────────────────────────────────

    def get_profile(self, user_id: str) -> UserProfile:
        """Get or create user profile."""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute("""
                SELECT user_id, display_name, department, role_context,
                       frequent_topics, preferred_sources, interaction_summary,
                       total_queries, last_active, created_at, metadata
                FROM user_profiles
                WHERE user_id = ?
            """, (user_id,)).fetchone()

        if not row:
            profile = UserProfile(user_id=user_id)
            self.save_profile(profile)
            return profile

        return UserProfile(
            user_id=row[0],
            display_name=row[1] or "",
            department=row[2] or "",
            role_context=row[3] or "",
            frequent_topics=json.loads(row[4] or "[]"),
            preferred_sources=json.loads(row[5] or "[]"),
            interaction_summary=row[6] or "",
            total_queries=row[7] or 0,
            last_active=row[8] or 0,
            created_at=row[9] or 0,
            metadata=json.loads(row[10] or "{}"),
        )

    def save_profile(self, profile: UserProfile):
        """Upsert a user profile."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO user_profiles
                (user_id, display_name, department, role_context,
                 frequent_topics, preferred_sources, interaction_summary,
                 total_queries, last_active, created_at, metadata)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """, (
                profile.user_id, profile.display_name, profile.department,
                profile.role_context, json.dumps(profile.frequent_topics),
                json.dumps(profile.preferred_sources), profile.interaction_summary,
                profile.total_queries, profile.last_active, profile.created_at,
                json.dumps(profile.metadata),
            ))
            conn.commit()

    def reset_profile(self, user_id: str):
        """Reset a user's learned preferences (keeps conversations)."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                UPDATE user_profiles SET
                    role_context = '',
                    frequent_topics = '[]',
                    preferred_sources = '[]',
                    interaction_summary = '',
                    metadata = '{}'
                WHERE user_id = ?
            """, (user_id,))
            conn.commit()

    # ── Analytics ─────────────────────────────────────────────────────────────

    def get_topic_frequency(self, user_id: str, limit: int = 10) -> list[dict]:
        """Get most frequently asked topics for a user."""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute("""
                SELECT query_intent, COUNT(*) as cnt
                FROM user_conversations
                WHERE user_id = ? AND role = 'user' AND query_intent != ''
                GROUP BY query_intent
                ORDER BY cnt DESC
                LIMIT ?
            """, (user_id, limit)).fetchall()
        return [{"intent": r[0], "count": r[1]} for r in rows]

    def get_interaction_stats(self, user_id: str) -> dict:
        """Get interaction statistics for a user."""
        profile = self.get_profile(user_id)
        sessions = self.list_sessions(user_id, limit=100)
        return {
            "total_queries": profile.total_queries,
            "total_sessions": len(sessions),
            "last_active": profile.last_active,
            "member_since": profile.created_at,
            "frequent_topics": profile.frequent_topics,
            "preferred_sources": profile.preferred_sources,
        }

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _row_to_turn(row: tuple) -> ConversationTurn:
        return ConversationTurn(
            id=row[0],
            user_id=row[1],
            session_id=row[2],
            role=row[3],
            content=row[4],
            query_intent=row[5] or "",
            timestamp=row[6],
            metadata=json.loads(row[7] or "{}"),
        )
