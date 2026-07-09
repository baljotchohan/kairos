"""
Decision graph — NetworkX-backed graph of decisions and their relationships.
Exports to an Obsidian vault so you can view the full decision web in Obsidian's Graph View.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import contextlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Optional

import networkx as nx

RelationType = Literal["same_topic", "caused_by", "same_person", "same_timeframe", "follow_up"]

# Every chat exchange gets auto-indexed as a DecisionNode (see
# orchestrator.py) so MCP's get_context can surface past KAIROS
# conversations to external clients like Claude Desktop. That's the right
# behavior for MCP — but feeding a user's own earlier chat messages back to
# them as "evidence" for an organizational decision (in the KAIROS web chat
# itself) reads as broken, not helpful. Interactive answer paths should
# exclude these via exclude_conversation_nodes(); MCP's get_context path
# intentionally does not.
CONVERSATION_TOPIC = "KAIROS Conversation"


def exclude_conversation_nodes(nodes: list["DecisionNode"]) -> list["DecisionNode"]:
    """Drop auto-indexed chat-history nodes from a retrieval result."""
    return [n for n in nodes if CONVERSATION_TOPIC not in (n.topics or [])]


@dataclass
class DecisionNode:
    id: str
    title: str
    summary: str
    date: str                   # ISO date string
    participants: list[str]
    source: str                 # e.g. "Slack #engineering", "Email thread"
    source_url: str
    topics: list[str]
    outcome: str
    raw_text: str = ""
    metadata: dict = field(default_factory=dict)
    user_id: str = ""

    def __post_init__(self):
        if self.participants is None:
            self.participants = []
        else:
            self.participants = [p for p in self.participants if p is not None]
        
        if self.topics is None:
            self.topics = []
        else:
            self.topics = [t for t in self.topics if t is not None]


class DecisionGraph:
    """
    Stores decisions as nodes and their relationships as edges.
    Persists to SQLite. Exports to Obsidian markdown vault.
    """

    def __init__(self, db_path: str = "./kairos.db"):
        self.graph = nx.DiGraph()
        self.db_path = db_path
        self._lock = threading.RLock()
        self._init_db()
        self._load_from_db()

    # ── SQLite Connections ───────────────────────────────────────────────────

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

    # ── Persistence ──────────────────────────────────────────────────────────

    def _init_db(self):
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS decisions (
                    id TEXT PRIMARY KEY,
                    title TEXT,
                    summary TEXT,
                    date TEXT,
                    participants TEXT,   -- JSON array
                    source TEXT,
                    source_url TEXT,
                    topics TEXT,         -- JSON array
                    outcome TEXT,
                    raw_text TEXT,
                    metadata TEXT        -- JSON object
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS relations (
                    from_id TEXT,
                    to_id TEXT,
                    relation_type TEXT,
                    PRIMARY KEY (from_id, to_id, relation_type)
                )
            """)
            # Schema Migration: Safely add user_id column if not exists. The
            # check-then-ALTER pattern isn't atomic — under concurrent first boot
            # two processes could both see it missing and both try to add it, so
            # the loser of the race must not crash startup.
            cursor = conn.execute("PRAGMA table_info(decisions)")
            columns = [info[1] for info in cursor.fetchall()]
            if "user_id" not in columns:
                try:
                    conn.execute("ALTER TABLE decisions ADD COLUMN user_id TEXT NOT NULL DEFAULT ''")
                except sqlite3.OperationalError:
                    pass

            # Create optimization indexes on decisions table to speed up query/timeline filtering
            conn.execute("CREATE INDEX IF NOT EXISTS idx_decisions_date ON decisions(date DESC)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_decisions_source_date ON decisions(source, date DESC)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_decisions_user_id ON decisions(user_id)")
            conn.commit()

    def _load_from_db(self):
        with self._lock:
            with self._get_connection() as conn:
                for row in conn.execute("SELECT id, title, summary, date, participants, source, source_url, topics, outcome, raw_text, metadata, user_id FROM decisions"):
                    node = DecisionNode(
                        id=row[0], title=row[1], summary=row[2], date=row[3],
                        participants=json.loads(row[4]), source=row[5],
                        source_url=row[6], topics=json.loads(row[7]),
                        outcome=row[8], raw_text=row[9],
                        metadata=json.loads(row[10]), user_id=row[11] if len(row) > 11 else "",
                    )
                    self.graph.add_node(node.id, data=node)

                for row in conn.execute("SELECT from_id, to_id, relation_type FROM relations"):
                    # Only add edge if both nodes have decision data (skip orphans)
                    if row[0] in self.graph and row[1] in self.graph:
                        if self.graph.has_edge(row[0], row[1]):
                            existing = self.graph.edges[row[0], row[1]].get("relations", [])
                            if row[2] not in existing:
                                existing.append(row[2])
                            self.graph.edges[row[0], row[1]]["relations"] = existing
                            self.graph.edges[row[0], row[1]]["relation"] = ", ".join(existing)
                        else:
                            self.graph.add_edge(row[0], row[1], relation=row[2], relations=[row[2]])

    def _save_node(self, node: DecisionNode):
        with self._get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO decisions (id, title, summary, date, participants, source, source_url, topics, outcome, raw_text, metadata, user_id)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                node.id, node.title, node.summary, node.date,
                json.dumps(node.participants), node.source, node.source_url,
                json.dumps(node.topics), node.outcome, node.raw_text,
                json.dumps(node.metadata), node.user_id,
            ))
            conn.commit()

    def _save_edge(self, from_id: str, to_id: str, relation: RelationType):
        with self._get_connection() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO relations VALUES (?,?,?)",
                (from_id, to_id, relation),
            )
            conn.commit()

    # ── Graph operations ──────────────────────────────────────────────────────

    def add_decision(self, node: DecisionNode, vault_path: str = None, user_id: Optional[str] = None):
        """
        Add a decision, auto-link it to existing nodes, and — if vault_path is
        given — immediately write/update only the affected Obsidian notes so the
        vault stays in sync without a full re-export.
        """
        if user_id and not node.user_id:
            node.user_id = user_id

        with self._lock:
            # Save to SQLite first (durable layer) to prevent desync if write fails
            self._save_node(node)
            self.graph.add_node(node.id, data=node)
            affected = self._auto_link(node)  # IDs of nodes that gained new edges

            if vault_path:
                # user_id is assumed to always be a Firebase UID, never raw user
                # input — but that assumption has exactly one exception in this
                # codebase (api/auth.py's `sim-`/`simulated-` DEBUG-only bypass,
                # which derives it from token content). Route it through the same
                # sanitizer used for decision titles so a user_id can never inject
                # path segments (e.g. "../../etc") into the vault path, regardless
                # of where it originated or whether that assumption ever breaks.
                uid_folder = f"KAIROS_{self._safe_filename(node.user_id)}" if node.user_id else "KAIROS_default"
                vault = Path(vault_path) / uid_folder
                vault.mkdir(parents=True, exist_ok=True)
                (vault / "KAIROS").mkdir(exist_ok=True)
                # Write the new node's note
                self._write_decision_note(vault, node)
                # Rewrite every neighbour whose "Related Decisions" section changed
                for nid in affected:
                    if nid in self.graph:
                        self._write_decision_note(vault, self.graph.nodes[nid]["data"])
                self._write_index_note(vault, user_id=node.user_id)

    def _same_user(self, from_id: str, to_id: str) -> bool:
        """Defense-in-depth: even though the only production caller (_auto_link)
        already filters to same-user pairs before reaching here, an edge-writer
        this close to the graph's core invariant should never trust a caller's
        pre-filtering alone."""
        a = self.graph.nodes[from_id].get("data")
        b = self.graph.nodes[to_id].get("data")
        return bool(a and b and a.user_id == b.user_id)

    def add_relation(self, from_id: str, to_id: str, relation: RelationType):
        with self._lock:
            if from_id not in self.graph or to_id not in self.graph:
                return
            if not self._same_user(from_id, to_id):
                return
            if self.graph.has_edge(from_id, to_id):
                existing = self.graph.edges[from_id, to_id].get("relations", [])
                if relation not in existing:
                    existing.append(relation)
                self.graph.edges[from_id, to_id]["relations"] = existing
                self.graph.edges[from_id, to_id]["relation"] = ", ".join(existing)
            else:
                self.graph.add_edge(from_id, to_id, relation=relation, relations=[relation])
            self._save_edge(from_id, to_id, relation)

    def add_relations_batch(self, relations_list: list[tuple[str, str, RelationType]]):
        """Batch insert relationships into both graph and SQLite in a single transaction."""
        with self._lock:
            valid_relations = []
            for from_id, to_id, relation in relations_list:
                if from_id not in self.graph or to_id not in self.graph:
                    continue
                if not self._same_user(from_id, to_id):
                    continue
                if self.graph.has_edge(from_id, to_id):
                    existing = self.graph.edges[from_id, to_id].get("relations", [])
                    if relation not in existing:
                        existing.append(relation)
                    self.graph.edges[from_id, to_id]["relations"] = existing
                    self.graph.edges[from_id, to_id]["relation"] = ", ".join(existing)
                else:
                    self.graph.add_edge(from_id, to_id, relation=relation, relations=[relation])
                valid_relations.append((from_id, to_id, relation))
            
            if not valid_relations:
                return
                
            with self._get_connection() as conn:
                conn.executemany(
                    "INSERT OR IGNORE INTO relations (from_id, to_id, relation_type) VALUES (?,?,?)",
                    valid_relations
                )
                conn.commit()

    def _load_node_from_db(self, decision_id: str):
        """Load a single node and its edges from the DB (for multi-worker sync)."""
        try:
            with self._get_connection() as conn:
                row = conn.execute(
                    "SELECT id, title, summary, date, participants, source, source_url, topics, outcome, raw_text, metadata, user_id "
                    "FROM decisions WHERE id = ?",
                    (decision_id,)
                ).fetchone()
                if not row:
                    return
                node = DecisionNode(
                    id=row[0], title=row[1], summary=row[2], date=row[3],
                    participants=json.loads(row[4]), source=row[5],
                    source_url=row[6], topics=json.loads(row[7]),
                    outcome=row[8], raw_text=row[9],
                    metadata=json.loads(row[10]), user_id=row[11] if len(row) > 11 else "",
                )
                self.graph.add_node(node.id, data=node)
                
                # Load relations where this node is involved
                for r_row in conn.execute(
                    "SELECT from_id, to_id, relation_type FROM relations WHERE from_id = ? OR to_id = ?",
                    (decision_id, decision_id)
                ):
                    if r_row[0] in self.graph and r_row[1] in self.graph:
                        if self.graph.has_edge(r_row[0], r_row[1]):
                            existing = self.graph.edges[r_row[0], r_row[1]].get("relations", [])
                            if r_row[2] not in existing:
                                existing.append(r_row[2])
                            self.graph.edges[r_row[0], r_row[1]]["relations"] = existing
                            self.graph.edges[r_row[0], r_row[1]]["relation"] = ", ".join(existing)
                        else:
                            self.graph.add_edge(r_row[0], r_row[1], relation=r_row[2], relations=[r_row[2]])
        except Exception as e:
            print(f"[Graph] _load_node_from_db error: {e}")

    def get_decision(self, decision_id: str, user_id: Optional[str] = None) -> Optional[DecisionNode]:
        with self._lock:
            if decision_id not in self.graph:
                self._load_node_from_db(decision_id)
            if decision_id not in self.graph:
                return None
            node = self.graph.nodes[decision_id].get("data")
            if user_id is not None and node and node.user_id != user_id:
                return None
            return node

    def get_connected(self, decision_id: str, depth: int = 2, user_id: Optional[str] = None) -> list[DecisionNode]:
        """Return all decisions reachable within `depth` hops, filtered by user_id."""
        with self._lock:
            if decision_id not in self.graph:
                return []
            root_node = self.graph.nodes[decision_id].get("data")
            if user_id is not None and root_node and root_node.user_id != user_id:
                return []
            reachable = nx.ego_graph(self.graph, decision_id, radius=depth, undirected=True)
            return [
                self.graph.nodes[n]["data"]
                for n in reachable.nodes
                if n != decision_id and "data" in self.graph.nodes[n]
                and (user_id is None or self.graph.nodes[n]["data"].user_id == user_id)
            ]

    def search_by_topic(self, topic: str, user_id: Optional[str] = None) -> list[DecisionNode]:
        topic_lower = topic.lower()
        with self._lock:
            return [
                self.graph.nodes[n]["data"]
                for n in self.graph.nodes
                if "data" in self.graph.nodes[n]
                and (user_id is None or self.graph.nodes[n]["data"].user_id == user_id)
                and any(topic_lower in t.lower() for t in self.graph.nodes[n]["data"].topics)
            ]

    def search_by_person(self, name: str, user_id: Optional[str] = None) -> list[DecisionNode]:
        name_lower = name.lower()
        with self._lock:
            return [
                self.graph.nodes[n]["data"]
                for n in self.graph.nodes
                if "data" in self.graph.nodes[n]
                and (user_id is None or self.graph.nodes[n]["data"].user_id == user_id)
                and any(name_lower in p.lower() for p in self.graph.nodes[n]["data"].participants)
            ]

    def get_edges_by_type(self, relation_type: RelationType, user_id: Optional[str] = None) -> list[tuple[DecisionNode, DecisionNode]]:
        """Return (from_node, to_node) pairs for every edge carrying `relation_type`,
        scoped to user_id (both endpoints must belong to that user)."""
        with self._lock:
            pairs: list[tuple[DecisionNode, DecisionNode]] = []
            for u, v, data in self.graph.edges(data=True):
                relations = data.get("relations") or [data.get("relation")]
                if relation_type not in relations:
                    continue
                nu = self.graph.nodes[u].get("data")
                nv = self.graph.nodes[v].get("data")
                if not nu or not nv:
                    continue
                if user_id is not None and (nu.user_id != user_id or nv.user_id != user_id):
                    continue
                pairs.append((nu, nv))
            return pairs

    def all_decisions(self, user_id: Optional[str] = None) -> list[DecisionNode]:
        # Excludes auto-indexed chat Q&A nodes (CONVERSATION_TOPIC) — those exist so
        # MCP's get_context (a different read path, via hybrid_search) can surface past
        # conversations to external clients, but every "list/count the decisions" view
        # in this app (Decision Index, Metrics tiles, debt score, pattern/risk scans)
        # should only ever see real decisions, not the user's own questions echoed back.
        with self._lock:
            return [
                self.graph.nodes[n]["data"]
                for n in self.graph.nodes
                if "data" in self.graph.nodes[n]
                and CONVERSATION_TOPIC not in (self.graph.nodes[n]["data"].topics or [])
                and (user_id is None or self.graph.nodes[n]["data"].user_id == user_id)
            ]

    def stats(self, user_id: Optional[str] = None) -> dict:
        with self._lock:
            keep_nodes = [
                n for n in self.graph.nodes
                if "data" in self.graph.nodes[n]
                and CONVERSATION_TOPIC not in (self.graph.nodes[n]["data"].topics or [])
                and (user_id is None or self.graph.nodes[n]["data"].user_id == user_id)
            ]
            subgraph = self.graph.subgraph(keep_nodes)
            return {
                "total_decisions": subgraph.number_of_nodes(),
                "total_relations": subgraph.number_of_edges(),
                "connected_components": nx.number_weakly_connected_components(subgraph) if keep_nodes else 0,
            }

    # ── Auto-linking ──────────────────────────────────────────────────────────

    def _auto_link(self, new_node: DecisionNode) -> set[str]:
        """Create edges for shared topics/participants. Returns IDs of nodes that gained edges."""
        affected: set[str] = set()
        relations_to_add: list[tuple[str, str, RelationType]] = []
        
        with self._lock:
            for existing_id in list(self.graph.nodes):
                if existing_id == new_node.id:
                    continue
                if "data" not in self.graph.nodes[existing_id]:
                    continue
                existing: DecisionNode = self.graph.nodes[existing_id]["data"]

                # Never link across users — a shared topic ("infrastructure") or a
                # common first name must not connect User A's decisions to User B's
                # (which would also leak B's titles into A's Obsidian notes).
                if existing.user_id != new_node.user_id:
                    continue

                shared_topics = set(t.lower() for t in new_node.topics) & set(t.lower() for t in existing.topics)
                if shared_topics:
                    relations_to_add.append((new_node.id, existing_id, "same_topic"))
                    affected.add(existing_id)

                shared_people = set(p.lower() for p in new_node.participants) & set(p.lower() for p in existing.participants)
                if shared_people:
                    relations_to_add.append((new_node.id, existing_id, "same_person"))
                    affected.add(existing_id)

            if relations_to_add:
                self.add_relations_batch(relations_to_add)

        return affected

    # ── Obsidian export ───────────────────────────────────────────────────────

    def export_to_obsidian(self, vault_path: str = "./obsidian_vault", user_id: Optional[str] = None):
        """
        Write one .md file per decision to vault_path / KAIROS_{user_id}.
        Obsidian's Graph View will render the [[wikilinks]] as a visual decision web.
        """
        with self._lock:
            # See add_decision()'s identical guard — sanitize before using
            # user_id as a filesystem path segment.
            uid_folder = f"KAIROS_{self._safe_filename(user_id)}" if user_id else "KAIROS_default"
            vault = Path(vault_path) / uid_folder
            vault.mkdir(parents=True, exist_ok=True)
            (vault / "KAIROS").mkdir(exist_ok=True)

            user_nodes = [
                n for n in self.graph.nodes
                if "data" in self.graph.nodes[n]
                and (user_id is None or self.graph.nodes[n]["data"].user_id == user_id)
            ]

            for node_id in user_nodes:
                node: DecisionNode = self.graph.nodes[node_id]["data"]
                self._write_decision_note(vault, node)

            self._write_index_note(vault, user_id=user_id)
            print(f"[KAIROS] Obsidian vault exported → {vault.resolve()}")
            print(f"         Open this folder in Obsidian and switch to Graph View.")

    def _safe_filename(self, title: str) -> str:
        return "".join(c if c.isalnum() or c in " -_" else "_" for c in title).strip()

    def _node_filename(self, node: DecisionNode) -> str:
        """Generates a collision-resistant filename by appending the first 8 chars of node UID."""
        safe_title = self._safe_filename(node.title)[:70]
        short_id = node.id[:8] if node.id else "unknown"
        return f"{safe_title}_{short_id}"

    def _write_decision_note(self, vault: Path, node: DecisionNode):
        filename = self._node_filename(node)
        filepath = vault / "KAIROS" / f"{filename}.md"

        with self._lock:
            # Outgoing edges from this node (same-user only — defense-in-depth so even
            # legacy cross-user edges created before the _auto_link fix never surface).
            outgoing = [
                (self.graph.nodes[t]["data"], self.graph.edges[node.id, t]["relation"])
                for t in self.graph.successors(node.id)
                if t in self.graph.nodes and self.graph.nodes[t]["data"].user_id == node.user_id
            ]
            # Incoming edges to this node
            incoming = [
                (self.graph.nodes[s]["data"], self.graph.edges[s, node.id]["relation"])
                for s in self.graph.predecessors(node.id)
                if s in self.graph.nodes and self.graph.nodes[s]["data"].user_id == node.user_id
            ]

        participant_links = " · ".join(f"[[{p}]]" for p in node.participants)
        topic_links = " ".join(f"#{'_'.join(t.split())}" for t in node.topics)

        related_section = ""
        if outgoing or incoming:
            related_section = "\n## Related Decisions\n"
            for related, relation in outgoing:
                label = self._node_filename(related)
                related_section += f"- [[{label}]] _{relation}_\n"
            for related, relation in incoming:
                label = self._node_filename(related)
                related_section += f"- [[{label}]] _{relation} (reverse)_\n"

        content = f"""---
kairos_id: {node.id}
date: {node.date}
source: "{node.source}"
topics: {json.dumps(node.topics)}
participants: {json.dumps(node.participants)}
---

# {node.title}

> {node.summary}

**Date:** {node.date}
**Participants:** {participant_links}
**Source:** [{node.source}]({node.source_url})
**Topics:** {topic_links}

## Outcome

{node.outcome}
{related_section}
---
*Indexed by KAIROS — Company Organizational Memory OS*
"""
        filepath.write_text(content, encoding="utf-8")

    def _write_index_note(self, vault: Path, user_id: Optional[str] = None):
        nodes = self.all_decisions(user_id=user_id)
        lines = [f"# KAIROS — Decision Index\n", f"**Total decisions:** {len(nodes)}\n\n"]

        by_topic: dict[str, list[DecisionNode]] = {}
        for n in nodes:
            for t in n.topics:
                by_topic.setdefault(t, []).append(n)

        for topic, decisions in sorted(by_topic.items()):
            lines.append(f"\n## {topic}\n")
            for d in decisions:
                label = self._node_filename(d)
                lines.append(f"- [[{label}]] · {d.date}\n")

        (vault / "KAIROS Index.md").write_text("".join(lines), encoding="utf-8")
