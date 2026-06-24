"""
Decision graph — NetworkX-backed graph of decisions and their relationships.
Exports to an Obsidian vault so you can view the full decision web in Obsidian's Graph View.
"""

import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Optional

import networkx as nx

RelationType = Literal["same_topic", "caused_by", "same_person", "same_timeframe", "follow_up"]


@dataclass
class DecisionNode:
    id: str
    title: str
    summary: str
    date: str                   # ISO date string
    participants: list[str]
    source: str                 # e.g. "Slack #engineering", "Email thread", "Meeting 2021-08-15"
    source_url: str
    topics: list[str]
    outcome: str
    raw_text: str = ""
    metadata: dict = field(default_factory=dict)


class DecisionGraph:
    """
    Stores decisions as nodes and their relationships as edges.
    Persists to SQLite. Exports to Obsidian markdown vault.
    """

    def __init__(self, db_path: str = "./kairos.db"):
        self.graph = nx.DiGraph()
        self.db_path = db_path
        self._init_db()
        self._load_from_db()

    # ── Persistence ──────────────────────────────────────────────────────────

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
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
            conn.commit()

    def _load_from_db(self):
        with sqlite3.connect(self.db_path) as conn:
            for row in conn.execute("SELECT * FROM decisions"):
                node = DecisionNode(
                    id=row[0], title=row[1], summary=row[2], date=row[3],
                    participants=json.loads(row[4]), source=row[5],
                    source_url=row[6], topics=json.loads(row[7]),
                    outcome=row[8], raw_text=row[9],
                    metadata=json.loads(row[10]),
                )
                self.graph.add_node(node.id, data=node)

            for row in conn.execute("SELECT from_id, to_id, relation_type FROM relations"):
                # Only add edge if both nodes have decision data (skip orphans)
                if row[0] in self.graph and row[1] in self.graph:
                    self.graph.add_edge(row[0], row[1], relation=row[2])

    def _save_node(self, node: DecisionNode):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO decisions VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """, (
                node.id, node.title, node.summary, node.date,
                json.dumps(node.participants), node.source, node.source_url,
                json.dumps(node.topics), node.outcome, node.raw_text,
                json.dumps(node.metadata),
            ))
            conn.commit()

    def _save_edge(self, from_id: str, to_id: str, relation: RelationType):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR IGNORE INTO relations VALUES (?,?,?)",
                (from_id, to_id, relation),
            )
            conn.commit()

    # ── Graph operations ──────────────────────────────────────────────────────

    def add_decision(self, node: DecisionNode, vault_path: str = None):
        """
        Add a decision, auto-link it to existing nodes, and — if vault_path is
        given — immediately write/update only the affected Obsidian notes so the
        vault stays in sync without a full re-export.
        """
        self.graph.add_node(node.id, data=node)
        self._save_node(node)
        affected = self._auto_link(node)  # IDs of nodes that gained new edges

        if vault_path:
            vault = Path(vault_path)
            vault.mkdir(parents=True, exist_ok=True)
            (vault / "KAIROS").mkdir(exist_ok=True)
            # Write the new node's note
            self._write_decision_note(vault, node)
            # Rewrite every neighbour whose "Related Decisions" section changed
            for nid in affected:
                if nid in self.graph:
                    self._write_decision_note(vault, self.graph.nodes[nid]["data"])
            self._write_index_note(vault)

    def add_relation(self, from_id: str, to_id: str, relation: RelationType):
        if from_id not in self.graph or to_id not in self.graph:
            return
        self.graph.add_edge(from_id, to_id, relation=relation)
        self._save_edge(from_id, to_id, relation)

    def get_decision(self, decision_id: str) -> Optional[DecisionNode]:
        if decision_id not in self.graph:
            return None
        return self.graph.nodes[decision_id].get("data")

    def get_connected(self, decision_id: str, depth: int = 2) -> list[DecisionNode]:
        """Return all decisions reachable within `depth` hops."""
        if decision_id not in self.graph:
            return []
        reachable = nx.ego_graph(self.graph, decision_id, radius=depth, undirected=True)
        return [
            self.graph.nodes[n]["data"]
            for n in reachable.nodes
            if n != decision_id and "data" in self.graph.nodes[n]
        ]

    def search_by_topic(self, topic: str) -> list[DecisionNode]:
        topic_lower = topic.lower()
        return [
            self.graph.nodes[n]["data"]
            for n in self.graph.nodes
            if "data" in self.graph.nodes[n]
            and any(topic_lower in t.lower() for t in self.graph.nodes[n]["data"].topics)
        ]

    def search_by_person(self, name: str) -> list[DecisionNode]:
        name_lower = name.lower()
        return [
            self.graph.nodes[n]["data"]
            for n in self.graph.nodes
            if "data" in self.graph.nodes[n]
            and any(name_lower in p.lower() for p in self.graph.nodes[n]["data"].participants)
        ]

    def all_decisions(self) -> list[DecisionNode]:
        return [
            self.graph.nodes[n]["data"]
            for n in self.graph.nodes
            if "data" in self.graph.nodes[n]
        ]

    def stats(self) -> dict:
        return {
            "total_decisions": self.graph.number_of_nodes(),
            "total_relations": self.graph.number_of_edges(),
            "connected_components": nx.number_weakly_connected_components(self.graph),
        }

    # ── Auto-linking ──────────────────────────────────────────────────────────

    def _auto_link(self, new_node: DecisionNode) -> set[str]:
        """Create edges for shared topics/participants. Returns IDs of nodes that gained edges."""
        affected: set[str] = set()
        for existing_id in list(self.graph.nodes):
            if existing_id == new_node.id:
                continue
            if "data" not in self.graph.nodes[existing_id]:
                continue
            existing: DecisionNode = self.graph.nodes[existing_id]["data"]

            shared_topics = set(t.lower() for t in new_node.topics) & set(t.lower() for t in existing.topics)
            if shared_topics:
                self.add_relation(new_node.id, existing_id, "same_topic")
                affected.add(existing_id)

            shared_people = set(p.lower() for p in new_node.participants) & set(p.lower() for p in existing.participants)
            if shared_people:
                self.add_relation(new_node.id, existing_id, "same_person")
                affected.add(existing_id)

        return affected

    # ── Obsidian export ───────────────────────────────────────────────────────

    def export_to_obsidian(self, vault_path: str = "./obsidian_vault"):
        """
        Write one .md file per decision to vault_path.
        Obsidian's Graph View will render the [[wikilinks]] as a visual decision web.

        Open the vault_path folder in Obsidian → Graph View → see all decisions connected.
        """
        vault = Path(vault_path)
        vault.mkdir(parents=True, exist_ok=True)
        (vault / "KAIROS").mkdir(exist_ok=True)

        for node_id in self.graph.nodes:
            node: DecisionNode = self.graph.nodes[node_id]["data"]
            self._write_decision_note(vault, node)

        self._write_index_note(vault)
        print(f"[KAIROS] Obsidian vault exported → {vault.resolve()}")
        print(f"         Open this folder in Obsidian and switch to Graph View.")

    def _safe_filename(self, title: str) -> str:
        return "".join(c if c.isalnum() or c in " -_" else "_" for c in title).strip()

    def _write_decision_note(self, vault: Path, node: DecisionNode):
        filename = self._safe_filename(node.title)[:80]
        filepath = vault / "KAIROS" / f"{filename}.md"

        # Outgoing edges from this node
        outgoing = [
            (self.graph.nodes[t]["data"], self.graph.edges[node.id, t]["relation"])
            for t in self.graph.successors(node.id)
            if t in self.graph.nodes
        ]
        # Incoming edges to this node
        incoming = [
            (self.graph.nodes[s]["data"], self.graph.edges[s, node.id]["relation"])
            for s in self.graph.predecessors(node.id)
            if s in self.graph.nodes
        ]

        participant_links = " · ".join(f"[[{p}]]" for p in node.participants)
        topic_links = " ".join(f"#{'_'.join(t.split())}" for t in node.topics)

        related_section = ""
        if outgoing or incoming:
            related_section = "\n## Related Decisions\n"
            for related, relation in outgoing:
                label = self._safe_filename(related.title)[:80]
                related_section += f"- [[{label}]] _{relation}_\n"
            for related, relation in incoming:
                label = self._safe_filename(related.title)[:80]
                related_section += f"- [[{label}]] _{relation} (reverse)_\n"

        content = f"""---
kairos_id: {node.id}
date: {node.date}
source: {node.source}
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

    def _write_index_note(self, vault: Path):
        nodes = self.all_decisions()
        lines = [f"# KAIROS — Decision Index\n", f"**Total decisions:** {len(nodes)}\n\n"]

        by_topic: dict[str, list[DecisionNode]] = {}
        for n in nodes:
            for t in n.topics:
                by_topic.setdefault(t, []).append(n)

        for topic, decisions in sorted(by_topic.items()):
            lines.append(f"\n## {topic}\n")
            for d in decisions:
                label = self._safe_filename(d.title)[:80]
                lines.append(f"- [[{label}]] · {d.date}\n")

        (vault / "KAIROS Index.md").write_text("".join(lines), encoding="utf-8")
