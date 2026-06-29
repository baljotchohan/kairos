"""
KAIROS dual-layer memory:
  - ChromaDB  → semantic / vector search ("find decisions about AWS")
  - SQLite    → structured queries ("decisions by John in Q3 2021")
  - graph.py  → relationship graph + Obsidian export

All three are written together on every store() call.
Embeddings powered by Fireworks AI (nomic-embed-text-v1.5 on AMD GPUs).
"""

import json
import sqlite3
import uuid
from typing import Optional

import chromadb
from chromadb import Documents, EmbeddingFunction, Embeddings

from openai import OpenAI

from config import config
from core.graph import DecisionGraph, DecisionNode


# ── Fireworks/Gemini embedding function for ChromaDB ─────────────────────────

class FireworksEmbeddingFunction(EmbeddingFunction):
    """ChromaDB-compatible embedding function backed by Gemini or Fireworks AI.
    Falls back to ChromaDB's built-in local embeddings when no API key is set
    (useful for local dev/testing without credentials)."""

    def __init__(self):
        self._local_fallback = not (config.GEMINI_API_KEY or config.FIREWORKS_API_KEY)

        if self._local_fallback:
            from chromadb.utils.embedding_functions import DefaultEmbeddingFunction
            self._local_ef = DefaultEmbeddingFunction()
            print("[Memory] No embedding API key — using local embeddings (lower quality, fine for dev)")
            return

        # Route to Gemini only if the key actually looks like a Google API key
        # (real Gemini keys start with "AIza"). A miskeyed value silently routes
        # to Fireworks, which has a valid embedding model — avoids hard failures.
        gemini_key = (config.GEMINI_API_KEY or "").strip()
        use_gemini = gemini_key.startswith("AIza")

        if use_gemini:
            self.api_key = gemini_key
            self.base_url = config.GEMINI_BASE_URL
            self.model = config.GEMINI_EMBED_MODEL
        else:
            if gemini_key and not use_gemini:
                print("[Memory] GEMINI_API_KEY does not look like a Gemini key — using Fireworks embeddings.")
            self.api_key = config.FIREWORKS_API_KEY
            self.base_url = config.FIREWORKS_BASE_URL
            self.model = config.FIREWORKS_EMBED_MODEL

        self._client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
        )

    def __call__(self, input: Documents) -> Embeddings:
        if self._local_fallback:
            return self._local_ef(input)
        try:
            response = self._client.embeddings.create(
                model=self.model,
                input=[text[:8000] for text in input],  # safe truncation
            )
            return [item.embedding for item in response.data]
        except Exception as e:
            # Never let an embedding API failure crash a live query or store.
            # Permanently switch this instance to local embeddings so every
            # subsequent call uses the same vector space (avoids dimension
            # mismatch between remote and local vectors mid-session).
            print(f"[Memory] Embedding API failed ({e}); switching to local embeddings.")
            from chromadb.utils.embedding_functions import DefaultEmbeddingFunction
            if not getattr(self, "_local_ef", None):
                self._local_ef = DefaultEmbeddingFunction()
            self._local_fallback = True
            return self._local_ef(input)


class KairosMemory:
    def __init__(
        self,
        chroma_path: str = None,
        db_path: str = None,
        obsidian_vault: str = None,
    ):
        self.obsidian_vault = obsidian_vault or config.OBSIDIAN_VAULT

        # ChromaDB — Fireworks-powered vector store
        self.chroma = chromadb.PersistentClient(path=chroma_path or config.CHROMA_PERSIST_DIR)
        self.collection = self.chroma.get_or_create_collection(
            name="decisions",
            embedding_function=FireworksEmbeddingFunction(),
            metadata={"hnsw:space": "cosine"},
        )

        # SQLite — structured store
        self.db_path = db_path or config.SQLITE_PATH
        self._init_sqlite()

        # NetworkX graph — relationships + Obsidian export
        self.graph = DecisionGraph(db_path=self.db_path)

    # ── Write ─────────────────────────────────────────────────────────────────

    def store(self, node: DecisionNode, user_id: Optional[str] = None):
        """Store a decision in all three layers and sync the Obsidian vault.

        Order matters: semantic_search resolves vector ids back through the
        SQLite-backed graph (graph.get_decision), so the durable layers are
        written FIRST. If a durable write fails we abort before creating an
        orphan vector; if the vector upsert fails last, the decision is still
        found via structured/graph search (degraded, not silently dropped)."""
        if user_id:
            node.user_id = user_id

        # 1. SQLite (structured queries) — durable source of truth
        self._sqlite_upsert(node)

        # 2. Graph + Obsidian — auto-links the node and writes only the changed notes
        self.graph.add_decision(node, vault_path=self.obsidian_vault, user_id=node.user_id)

        # 3. ChromaDB (vector search) — written LAST so a failure can't orphan a
        #    vector whose id resolves to a missing decision (silent drop in search).
        doc_text = f"{node.title}\n{node.summary}\n{node.outcome}\n{' '.join(node.topics)}"
        self.collection.upsert(
            ids=[node.id],
            documents=[doc_text],
            metadatas=[{
                "title": node.title,
                "date": node.date,
                "source": node.source,
                "participants": json.dumps(node.participants),
                "topics": json.dumps(node.topics),
                "user_id": node.user_id,
            }],
        )

    # ── Read ──────────────────────────────────────────────────────────────────

    def semantic_search(self, query: str, n_results: int = 5, user_id: Optional[str] = None) -> list[DecisionNode]:
        """Vector similarity search — best for open-ended NL queries."""
        # Fail CLOSED: never return every tenant's vectors when user_id is missing.
        if not user_id:
            print("[Memory] semantic_search called without user_id — returning [] (fail-closed).")
            return []
        where_filter = {"user_id": user_id}
        results = self.collection.query(
            query_texts=[query], 
            n_results=n_results,
            where=where_filter
        )
        ids = results["ids"][0] if results["ids"] else []
        return [n for i in ids if (n := self.graph.get_decision(i, user_id=user_id))]

    def structured_search(
        self,
        topic: Optional[str] = None,
        person: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> list[DecisionNode]:
        """SQL-backed exact / range queries."""
        # Fail CLOSED: never return every tenant's rows when user_id is missing.
        if not user_id:
            print("[Memory] structured_search called without user_id — returning [] (fail-closed).")
            return []
        clauses, params = [], []
        if topic:
            clauses.append("topics LIKE ?")
            params.append(f"%{topic}%")
        if person:
            clauses.append("participants LIKE ?")
            params.append(f"%{person}%")
        if date_from:
            clauses.append("date >= ?")
            params.append(date_from)
        if date_to:
            clauses.append("date <= ?")
            params.append(date_to)
        if user_id:
            clauses.append("user_id = ?")
            params.append(user_id)

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._connect() as conn:
            rows = conn.execute(f"SELECT id FROM decisions {where}", params).fetchall()
        return [n for row in rows if (n := self.graph.get_decision(row[0], user_id=user_id))]

    def hybrid_search(self, query: str, n_results: int = 5, user_id: Optional[str] = None) -> list[DecisionNode]:
        """
        Combines semantic (vector) search, keyword SQL search, source filter, and recency boost.
        Scoped to a single user and FAILS CLOSED: without a user_id we return nothing
        rather than leak every user's decisions. The query path always passes a real
        uid, so this only catches future regressions / misuse.
        """
        from datetime import datetime

        if not user_id:
            print("[Memory] hybrid_search called without user_id — returning [] (fail-closed).")
            return []

        # 1. Semantic Search
        semantic_nodes = self.semantic_search(query, n_results=n_results * 2, user_id=user_id)

        # 2. Keyword + source-aware SQL search
        words = [w.strip(",.?!\"'()").lower() for w in query.split() if len(w) > 3]
        sql_nodes = []
        source_nodes = []

        # Source filter: if query mentions a data source, include all decisions from it
        SOURCE_KEYWORDS = {
            "slack": "slack", "email": "email", "drive": "drive",
            "jira": "jira", "zoom": "zoom", "meeting": "meeting",
        }
        for kw, src in SOURCE_KEYWORDS.items():
            if kw in query.lower():
                source_nodes.extend(self._search_by_source(src, user_id=user_id))

        if words:
            for word in words[:4]:
                if word not in SOURCE_KEYWORDS:
                    sql_nodes.extend(self.structured_search(topic=word, user_id=user_id))
                    sql_nodes.extend(self.structured_search(person=word, user_id=user_id))

        # 3. Graph neighbors of top semantic results
        graph_nodes = []
        for node in semantic_nodes[:3]:
            graph_nodes.extend(self.graph.get_connected(node.id, depth=1, user_id=user_id))

        # 4. Merge, score, and apply recency boost
        all_nodes: dict[str, DecisionNode] = {}
        for node in semantic_nodes + sql_nodes + source_nodes + graph_nodes:
            all_nodes[node.id] = node

        today = datetime.utcnow().date()
        scores: dict[str, float] = {}
        for nid, node in all_nodes.items():
            score = 0.0
            if node in semantic_nodes:
                idx = semantic_nodes.index(node)
                score += 1.0 - (idx / max(len(semantic_nodes), 1))
            else:
                score += 0.2

            if node in sql_nodes:
                score += 0.3

            if node in source_nodes:
                score += 0.4  # strong boost for source-matched decisions

            # Recency boost: decisions from the last 7 days score higher
            try:
                decision_date = datetime.strptime(node.date, "%Y-%m-%d").date()
                days_ago = (today - decision_date).days
                if days_ago <= 7:
                    score += 0.5 - (days_ago * 0.07)  # max +0.5 for today
            except (ValueError, TypeError):
                pass

            # Graph connectivity boost
            neighbors = [n.id for n in self.graph.get_connected(node.id, depth=1, user_id=user_id)]
            connected = sum(1 for nid2 in neighbors if nid2 in all_nodes)
            score += 0.1 * connected

            scores[nid] = score

        sorted_ids = sorted(scores, key=scores.get, reverse=True)
        return [all_nodes[nid] for nid in sorted_ids[:n_results]]

    def _search_by_source(self, source_keyword: str, user_id: Optional[str] = None) -> list[DecisionNode]:
        """Return all decisions whose source contains source_keyword."""
        query = "SELECT id FROM decisions WHERE source LIKE ?"
        params = [f"%{source_keyword}%"]
        if user_id:
            query += " AND user_id = ?"
            params.append(user_id)
        query += " ORDER BY date DESC LIMIT 20"

        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [n for row in rows if (n := self.graph.get_decision(row[0], user_id=user_id))]

    # ── Inventory cache (raw item snapshots, no LLM) ───────────────────────────

    def store_inventory(self, user_id: str, items: list[dict]):
        """Upsert lightweight inventory rows for a user. Each item:
        {source, item_id, title, url, date, kind, snippet}. Never raises."""
        if not user_id or not items:
            return
        from datetime import datetime
        now = datetime.utcnow().isoformat()
        try:
            with self._connect() as conn:
                conn.executemany("""
                    INSERT OR REPLACE INTO inventory
                    (user_id, source, item_id, title, url, item_date, kind, snippet, fetched_at)
                    VALUES (?,?,?,?,?,?,?,?,?)
                """, [
                    (
                        user_id, it.get("source", ""), str(it.get("item_id", "")),
                        (it.get("title") or "")[:300], it.get("url", ""),
                        it.get("date", ""), it.get("kind", ""),
                        (it.get("snippet") or "")[:500], now,
                    )
                    for it in items if it.get("item_id")
                ])
                conn.commit()
        except Exception as e:
            print(f"[Memory] store_inventory error: {e}")

    def search_inventory(
        self, user_id: str, query: Optional[str] = None,
        source: Optional[str] = None, limit: int = 20,
    ) -> list[dict]:
        """Read a user's cached inventory (instant 'what do I have' fallback)."""
        if not user_id:
            return []
        clauses = ["user_id = ?"]
        params: list = [user_id]
        if source:
            clauses.append("source LIKE ?")
            params.append(f"%{source}%")
        if query:
            clauses.append("(title LIKE ? OR snippet LIKE ?)")
            params.extend([f"%{query}%", f"%{query}%"])
        where = " AND ".join(clauses)
        try:
            with self._connect() as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(
                    f"SELECT source, item_id, title, url, item_date, kind, snippet "
                    f"FROM inventory WHERE {where} ORDER BY item_date DESC LIMIT ?",
                    params + [limit],
                ).fetchall()
                return [dict(r) for r in rows]
        except Exception as e:
            print(f"[Memory] search_inventory error: {e}")
            return []

    def inventory_counts(self, user_id: str) -> dict:
        """Per-source counts of a user's cached inventory items."""
        if not user_id:
            return {}
        try:
            with self._connect() as conn:
                rows = conn.execute(
                    "SELECT source, COUNT(*) FROM inventory WHERE user_id = ? GROUP BY source",
                    (user_id,),
                ).fetchall()
                return {r[0]: r[1] for r in rows}
        except Exception as e:
            print(f"[Memory] inventory_counts error: {e}")
            return {}

    def get_user_context(self, user_id: str) -> str:
        """Loads the user profile context and recent history summary from UserMemory."""
        from core.user_memory import UserMemory
        um = UserMemory(db_path=self.db_path)
        profile = um.get_profile(user_id)
        history = um.get_current_session_context(user_id, max_turns=5)
        
        context_parts = []
        if profile.role_context:
            context_parts.append(f"User role context: {profile.role_context}")
        if profile.frequent_topics:
            context_parts.append(f"Frequently asked topics: {', '.join(profile.frequent_topics)}")
        if profile.interaction_summary:
            context_parts.append(f"Recent profile summary: {profile.interaction_summary}")
            
        history_str = ""
        if history:
            history_str = "\n".join([f"{h['role']}: {h['content']}" for h in history])
            
        profile_str = "\n".join(context_parts)
        return f"User Profile Context:\n{profile_str}\n\nRecent History:\n{history_str}"

    def get_context(self, query: str, n_results: int = 5, user_id: Optional[str] = None) -> list[dict]:
        """MCP tool: returns serialisable list for get_context() MCP call."""
        nodes = self.semantic_search(query, n_results=n_results, user_id=user_id)
        return [
            {
                "id": n.id,
                "title": n.title,
                "summary": n.summary,
                "date": n.date,
                "source": n.source,
                "participants": n.participants,
                "outcome": n.outcome,
                "related": [r.id for r in self.graph.get_connected(n.id, depth=1, user_id=user_id)],
            }
            for n in nodes
        ]

    def rebuild_obsidian(self, user_id: Optional[str] = None):
        """Full vault rebuild — use after bulk imports or if vault gets out of sync."""
        self.graph.export_to_obsidian(self.obsidian_vault, user_id=user_id)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _connect(self) -> sqlite3.Connection:
        """SQLite connection with WAL + busy timeout so concurrent async writes
        don't raise 'database is locked' (matches graph.py / user_memory.py)."""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA busy_timeout=30000;")
        return conn

    def _init_sqlite(self):
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS decisions (
                    id TEXT PRIMARY KEY,
                    title TEXT,
                    summary TEXT,
                    date TEXT,
                    participants TEXT,
                    source TEXT,
                    source_url TEXT,
                    topics TEXT,
                    outcome TEXT,
                    raw_text TEXT,
                    metadata TEXT
                )
            """)
            # Schema Migration: Safely add user_id column if not exists
            cursor = conn.execute("PRAGMA table_info(decisions)")
            columns = [info[1] for info in cursor.fetchall()]
            if "user_id" not in columns:
                conn.execute("ALTER TABLE decisions ADD COLUMN user_id TEXT NOT NULL DEFAULT ''")

            # Inventory: lightweight, per-user snapshot of raw items seen during
            # ingestion (files/emails/messages/issues/recordings). No LLM — just
            # metadata — so the agent can answer "what do I have" instantly/offline
            # as a cache alongside live connector lookups.
            conn.execute("""
                CREATE TABLE IF NOT EXISTS inventory (
                    user_id    TEXT NOT NULL,
                    source     TEXT NOT NULL,
                    item_id    TEXT NOT NULL,
                    title      TEXT,
                    url        TEXT,
                    item_date  TEXT,
                    kind       TEXT,
                    snippet    TEXT,
                    fetched_at TEXT,
                    PRIMARY KEY (user_id, item_id)
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_inventory_user ON inventory(user_id, source)")
            conn.commit()

    def _sqlite_upsert(self, node: DecisionNode):
        with self._connect() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO decisions
                (id, title, summary, date, participants, source, source_url, topics, outcome, raw_text, metadata, user_id)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                node.id, node.title, node.summary, node.date,
                json.dumps(node.participants), node.source,
                node.source_url, json.dumps(node.topics), node.outcome,
                node.raw_text, json.dumps(node.metadata), node.user_id,
            ))
            conn.commit()

    @staticmethod
    def make_id(title: str | None = None, source_url: str | None = None, user_id: str | None = None) -> str:
        # Namespace the deterministic ID by user_id so two users who ingest the SAME
        # public doc/link (or a shared "Untitled" title) never produce the same id and
        # silently overwrite each other's decision (INSERT OR REPLACE / vector upsert).
        # Missing user_id → random uuid, so unauthenticated ingests can't collide either.
        if title and source_url and user_id:
            import uuid
            namespace = uuid.UUID("3c8f8d22-1d57-4b77-84a1-f761d4aef822")
            unique_key = f"{user_id.strip().lower()}:{title.strip().lower()}:{source_url.strip().lower()}"
            return str(uuid.uuid5(namespace, unique_key))
        return str(uuid.uuid4())
