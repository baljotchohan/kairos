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

        # Route to Gemini if configured, otherwise Fireworks
        if config.GEMINI_API_KEY:
            self.api_key = config.GEMINI_API_KEY
            self.base_url = config.GEMINI_BASE_URL
            self.model = config.GEMINI_EMBED_MODEL
        else:
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
        response = self._client.embeddings.create(
            model=self.model,
            input=[text[:8000] for text in input],  # safe truncation
        )
        return [item.embedding for item in response.data]


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

    def store(self, node: DecisionNode):
        """Store a decision in all three layers and sync the Obsidian vault."""
        # 1. ChromaDB (vector search)
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
            }],
        )

        # 2. SQLite (structured queries)
        self._sqlite_upsert(node)

        # 3. Graph + Obsidian — auto-links the node and writes only the changed notes
        self.graph.add_decision(node, vault_path=self.obsidian_vault)

    # ── Read ──────────────────────────────────────────────────────────────────

    def semantic_search(self, query: str, n_results: int = 5) -> list[DecisionNode]:
        """Vector similarity search — best for open-ended NL queries."""
        results = self.collection.query(query_texts=[query], n_results=n_results)
        ids = results["ids"][0] if results["ids"] else []
        return [n for i in ids if (n := self.graph.get_decision(i))]

    def structured_search(
        self,
        topic: Optional[str] = None,
        person: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> list[DecisionNode]:
        """SQL-backed exact / range queries."""
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

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(f"SELECT id FROM decisions {where}", params).fetchall()
        return [n for row in rows if (n := self.graph.get_decision(row[0]))]

    def hybrid_search(self, query: str, n_results: int = 5) -> list[DecisionNode]:
        """
        Combines semantic (vector) search, keyword SQL search, source filter, and recency boost.
        """
        from datetime import datetime

        # 1. Semantic Search
        semantic_nodes = self.semantic_search(query, n_results=n_results * 2)

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
                source_nodes.extend(self._search_by_source(src))

        if words:
            for word in words[:4]:
                if word not in SOURCE_KEYWORDS:
                    sql_nodes.extend(self.structured_search(topic=word))
                    sql_nodes.extend(self.structured_search(person=word))

        # 3. Graph neighbors of top semantic results
        graph_nodes = []
        for node in semantic_nodes[:3]:
            graph_nodes.extend(self.graph.get_connected(node.id, depth=1))

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
            neighbors = [n.id for n in self.graph.get_connected(node.id, depth=1)]
            connected = sum(1 for nid2 in neighbors if nid2 in all_nodes)
            score += 0.1 * connected

            scores[nid] = score

        sorted_ids = sorted(scores, key=scores.get, reverse=True)
        return [all_nodes[nid] for nid in sorted_ids[:n_results]]

    def _search_by_source(self, source_keyword: str) -> list[DecisionNode]:
        """Return all decisions whose source contains source_keyword."""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT id FROM decisions WHERE source LIKE ? ORDER BY date DESC LIMIT 20",
                (f"%{source_keyword}%",),
            ).fetchall()
        return [n for row in rows if (n := self.graph.get_decision(row[0]))]

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

    def get_context(self, query: str, n_results: int = 5) -> list[dict]:
        """MCP tool: returns serialisable list for get_context() MCP call."""
        nodes = self.semantic_search(query, n_results=n_results)
        return [
            {
                "id": n.id,
                "title": n.title,
                "summary": n.summary,
                "date": n.date,
                "source": n.source,
                "participants": n.participants,
                "outcome": n.outcome,
                "related": [r.id for r in self.graph.get_connected(n.id, depth=1)],
            }
            for n in nodes
        ]

    def rebuild_obsidian(self):
        """Full vault rebuild — use after bulk imports or if vault gets out of sync."""
        self.graph.export_to_obsidian(self.obsidian_vault)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _init_sqlite(self):
        with sqlite3.connect(self.db_path) as conn:
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
            conn.commit()

    def _sqlite_upsert(self, node: DecisionNode):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO decisions
                (id, title, summary, date, participants, source, source_url, topics, outcome, raw_text, metadata)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """, (
                node.id, node.title, node.summary, node.date,
                json.dumps(node.participants), node.source,
                node.source_url, json.dumps(node.topics), node.outcome,
                node.raw_text, json.dumps(node.metadata),
            ))
            conn.commit()

    @staticmethod
    def make_id() -> str:
        return str(uuid.uuid4())
