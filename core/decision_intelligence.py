"""
KAIROS Decision Intelligence — proactive analysis on top of the existing
decisions/relations tables. No new storage: every function here only reads
through `KairosMemory` / `DecisionGraph` and, where noted, makes ONE batched
LLM call via `core.fireworks.fireworks` (Fireworks -> Groq -> Gemini chain).

Every function takes and enforces `user_id` — fails closed (empty result)
without one, matching memory.py/graph.py's multi-tenancy guarantee.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Optional

from core.fireworks import fireworks
from core.graph import DecisionNode, exclude_conversation_nodes

IMPACT_KEYWORDS = (
    "budget", "cost", "$", "vendor", "contract", "security", "compliance",
    "layoff", "funding", "revenue", "legal", "acquisition", "outage", "breach",
)

STALE_TOPIC_KEYWORDS = ("vendor", "contract", "subscription", "license", "renewal")


def _extract_json(raw: str):
    """Best-effort JSON extraction from an LLM response (mirrors synthesis_agent's parsing)."""
    raw = raw.strip()
    match = re.search(r"(\{.*\}|\[.*\])", raw, re.DOTALL)
    text = match.group(1) if match else raw
    return json.loads(text)


def _days_since(date_str: str) -> Optional[int]:
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - d).days
    except (ValueError, TypeError):
        return None


def _node_blob(n: DecisionNode) -> str:
    return f"{n.title} {n.summary} {n.outcome} {' '.join(n.topics)} {json.dumps(n.metadata or {})}".lower()


def _has_impact_keywords(n: DecisionNode) -> bool:
    blob = _node_blob(n)
    return any(kw in blob for kw in IMPACT_KEYWORDS)


# ── 1.1 find_similar_decisions ────────────────────────────────────────────────

async def find_similar_decisions(memory, user_id: Optional[str], query: str, limit: int = 5) -> dict:
    """Semantic-search candidates, then have the LLM decide which are genuine
    precedent vs. topically-similar noise. Returns a punchy one-line verdict."""
    if not user_id or not query:
        return {"matches": [], "verdict": "No user context or query provided."}

    candidates = memory.semantic_search(query, n_results=max(limit * 2, 8), user_id=user_id)
    candidates = exclude_conversation_nodes(candidates)
    if not candidates:
        return {"matches": [], "verdict": "No precedent found — this looks like new territory."}

    candidate_block = "\n\n".join(
        f"[{i}] {c.title}\nDate: {c.date}\nSummary: {c.summary}\nOutcome: {c.outcome or 'unknown'}\nTopics: {', '.join(c.topics)}"
        for i, c in enumerate(candidates)
    )
    prompt = f"""New situation: "{query}"

Candidate past decisions (topically similar, retrieved by search):
---
{candidate_block}
---

For each candidate, judge whether it is a genuine precedent for the new situation
(same underlying problem or choice being weighed) versus just topically-similar noise.
Return ONLY this JSON, no markdown:
{{"relevant_indices": [<ints of genuine precedents, best match first>], "verdict": "<one punchy sentence: was this tried before, what happened, what to do now>"}}
If none are genuine precedents, return {{"relevant_indices": [], "verdict": "<one sentence saying no real precedent exists>"}}."""

    try:
        raw = await fireworks.complete(
            prompt,
            system="You are a sharp analyst separating genuine organizational precedent from topical noise. Be direct and decisive, never hedge.",
            max_tokens=500,
        )
        parsed = _extract_json(raw)
        relevant_indices = [i for i in parsed.get("relevant_indices", []) if isinstance(i, int) and 0 <= i < len(candidates)]
        verdict = parsed.get("verdict") or "No clear verdict could be formed."
    except Exception as e:
        import sys
        print(f"[DecisionIntelligence] find_similar_decisions LLM error: {e}", file=sys.stderr)
        # Fail soft: surface raw semantic matches without a verdict rather than nothing.
        relevant_indices = list(range(min(limit, len(candidates))))
        verdict = "Precedent found (verdict unavailable — analysis model errored)."

    matches = []
    for rank, idx in enumerate(relevant_indices[:limit]):
        n = candidates[idx]
        matches.append({
            "decision_id": n.id,
            "title": n.title,
            "summary": n.summary,
            "date": n.date,
            "similarity_score": round(max(0.0, 1.0 - (idx / max(len(candidates), 1))), 2),
            "outcome": n.outcome,
            "source_url": n.source_url,
        })

    return {"matches": matches, "verdict": verdict}


# ── 1.2 detect_decision_patterns ──────────────────────────────────────────────

def _scoped_decisions(memory, user_id: str, scope: Optional[str], lookback_days: Optional[int]) -> list[DecisionNode]:
    nodes = memory.graph.all_decisions(user_id=user_id)
    if scope and scope.lower() != "all":
        scope_lower = scope.lower()
        nodes = [n for n in nodes if scope_lower in [t.lower() for t in n.topics]]
    if lookback_days:
        nodes = [n for n in nodes if (d := _days_since(n.date)) is None or d <= lookback_days]
    return nodes


def _union_find_clusters(pairs: list[tuple[DecisionNode, DecisionNode]]) -> list[list[DecisionNode]]:
    parent: dict[str, str] = {}
    by_id: dict[str, DecisionNode] = {}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for a, b in pairs:
        for n in (a, b):
            if n.id not in parent:
                parent[n.id] = n.id
                by_id[n.id] = n
        union(a.id, b.id)

    clusters: dict[str, list[DecisionNode]] = {}
    for nid in parent:
        root = find(nid)
        clusters.setdefault(root, []).append(by_id[nid])
    return list(clusters.values())


def _severity(nodes: list[DecisionNode], base: int = 0) -> str:
    """Deterministic severity heuristic — count of affected decisions + impact
    keywords + recency. The LLM never invents severity, only prose."""
    score = base + min(len(nodes), 5) * 10
    if any(_has_impact_keywords(n) for n in nodes):
        score += 25
    oldest_days = max((d for n in nodes if (d := _days_since(n.date)) is not None), default=0)
    if oldest_days > 730:
        score += 15
    elif oldest_days > 365:
        score += 8
    if score >= 55:
        return "high"
    if score >= 30:
        return "medium"
    return "low"


def _contradiction_clusters(memory, user_id: str, scoped_ids: set[str]) -> list[list[DecisionNode]]:
    """same_topic-connected clusters (2+) whose members have distinct, non-empty outcomes."""
    pairs = memory.graph.get_edges_by_type("same_topic", user_id=user_id)
    pairs = [(a, b) for a, b in pairs if a.id in scoped_ids and b.id in scoped_ids]
    clusters = _union_find_clusters(pairs)
    out = []
    for cluster in clusters:
        outcomes = {n.outcome.strip().lower() for n in cluster if n.outcome and n.outcome.strip()}
        if len(cluster) >= 2 and len(outcomes) > 1:
            out.append(cluster)
    return out


def _stale_vendor_decisions(memory, user_id: str, scoped: list[DecisionNode]) -> list[DecisionNode]:
    follow_up_pairs = memory.graph.get_edges_by_type("follow_up", user_id=user_id)
    has_follow_up = {n.id for pair in follow_up_pairs for n in pair}
    stale = []
    for n in scoped:
        blob = _node_blob(n)
        if not any(kw in blob for kw in STALE_TOPIC_KEYWORDS):
            continue
        if n.id in has_follow_up:
            continue
        days = _days_since(n.date)
        if days is not None and days >= 365:
            stale.append(n)
    return stale


def _bus_factor_clusters(scoped: list[DecisionNode]) -> list[list[DecisionNode]]:
    by_maker: dict[str, list[DecisionNode]] = {}
    for n in scoped:
        maker = (n.metadata or {}).get("decision_maker", "").strip().lower()
        if maker:
            by_maker.setdefault(maker, []).append(n)
    return [ns for ns in by_maker.values() if len(ns) >= 3]


async def detect_decision_patterns(memory, user_id: Optional[str], scope: str = "all", lookback_days: int = 365) -> dict:
    if not user_id:
        return {"patterns": []}

    scoped = _scoped_decisions(memory, user_id, scope, lookback_days)
    scoped_ids = {n.id for n in scoped}
    if not scoped:
        return {"patterns": []}

    flagged: list[dict] = []
    for cluster in _contradiction_clusters(memory, user_id, scoped_ids):
        flagged.append({"pattern_type": "contradictory_outcome", "nodes": cluster})
    stale_vendors = _stale_vendor_decisions(memory, user_id, scoped)
    if stale_vendors:
        flagged.append({"pattern_type": "unreviewed_vendor_spend", "nodes": stale_vendors})
    for cluster in _bus_factor_clusters(scoped):
        flagged.append({"pattern_type": "bus_factor_risk", "nodes": cluster})

    if not flagged:
        return {"patterns": []}

    # Pre-compute deterministic severity before asking the LLM for prose only.
    for f in flagged:
        f["severity"] = _severity(f["nodes"])

    cluster_block = "\n\n".join(
        f"[{i}] type={f['pattern_type']} severity={f['severity']} decisions="
        + "; ".join(f"{n.title} ({n.date}, outcome: {n.outcome[:80] or 'n/a'})" for n in f["nodes"][:6])
        for i, f in enumerate(flagged)
    )
    prompt = f"""Flagged organizational patterns (already detected structurally, severity already scored):
---
{cluster_block}
---

For EACH numbered pattern, write a natural-language description and a concrete recommendation.
Return ONLY this JSON array, one object per pattern index in order:
[{{"description": "...", "recommendation": "..."}}, ...]
Be specific — name the decisions/people/topics involved. Do not invent facts not present above."""

    try:
        raw = await fireworks.complete(
            prompt,
            system="You are KAIROS's pattern-detection analyst. You write sharp, specific, non-generic organizational risk descriptions.",
            max_tokens=1200,
        )
        write_ups = _extract_json(raw)
        if not isinstance(write_ups, list):
            write_ups = []
    except Exception as e:
        import sys
        print(f"[DecisionIntelligence] detect_decision_patterns LLM error: {e}", file=sys.stderr)
        write_ups = []

    patterns = []
    for i, f in enumerate(flagged):
        wu = write_ups[i] if i < len(write_ups) and isinstance(write_ups[i], dict) else {}
        patterns.append({
            "pattern_type": f["pattern_type"],
            "description": wu.get("description") or f"{len(f['nodes'])} decisions flagged as {f['pattern_type'].replace('_', ' ')}.",
            "affected_decisions": [n.id for n in f["nodes"]],
            "severity": f["severity"],
            "recommendation": wu.get("recommendation") or "Review these decisions with the relevant stakeholders.",
        })

    patterns.sort(key=lambda p: {"high": 0, "medium": 1, "low": 2}.get(p["severity"], 3))
    return {"patterns": patterns}


# ── 1.3 predict_decision_risk ─────────────────────────────────────────────────

def _risk_score(n: DecisionNode, has_follow_up: set[str]) -> tuple[int, list[str]]:
    score = 0
    reasons = []
    days = _days_since(n.date)
    if n.id not in has_follow_up:
        if days is not None and days > 730:
            score += 45
            reasons.append(f"No review or follow-up in over {days // 365} years")
        elif days is not None and days > 365:
            score += 30
            reasons.append("No review or follow-up in over a year")
        elif days is not None and days > 180:
            score += 15
            reasons.append("No review or follow-up in 6+ months")
    if _has_impact_keywords(n):
        score += 25
        reasons.append("Involves budget/vendor/security/compliance impact")
    if not (n.metadata or {}).get("decision_maker"):
        score += 5
        reasons.append("No clear decision owner on record")
    return min(score, 100), reasons


async def predict_decision_risk(memory, user_id: Optional[str], decision_id: Optional[str] = None, scope: str = "all") -> dict:
    if not user_id:
        return {"at_risk": []}

    if decision_id:
        node = memory.graph.get_decision(decision_id, user_id=user_id)
        scoped = [node] if node else []
    else:
        scoped = _scoped_decisions(memory, user_id, scope, lookback_days=None)
    if not scoped:
        return {"at_risk": []}

    follow_up_pairs = memory.graph.get_edges_by_type("follow_up", user_id=user_id)
    has_follow_up = {n.id for pair in follow_up_pairs for n in pair}

    scored = []
    for n in scoped:
        score, reasons = _risk_score(n, has_follow_up)
        if score > 0:
            scored.append((n, score, reasons))
    scored.sort(key=lambda t: t[1], reverse=True)

    # Batch one LLM call to write recommendations for only the top N — keeps cost flat.
    top_n = scored[:10]
    recommendations: dict[str, str] = {}
    if top_n:
        block = "\n\n".join(
            f"[{i}] {n.title} (risk={score}) — reasons: {', '.join(reasons)}. Outcome: {n.outcome[:120] or 'n/a'}"
            for i, (n, score, reasons) in enumerate(top_n)
        )
        prompt = f"""These decisions were scored as at-risk (score already computed, do not change it):
---
{block}
---
For each, write ONE short actionable recommendation. Return ONLY JSON:
[{{"recommendation": "..."}}, ...] in the same order."""
        try:
            raw = await fireworks.complete(
                prompt,
                system="You write terse, actionable one-line recommendations for organizational decision review.",
                max_tokens=800,
            )
            parsed = _extract_json(raw)
            if isinstance(parsed, list):
                for i, item in enumerate(parsed):
                    if i < len(top_n) and isinstance(item, dict):
                        recommendations[top_n[i][0].id] = item.get("recommendation", "")
        except Exception as e:
            import sys
            print(f"[DecisionIntelligence] predict_decision_risk LLM error: {e}", file=sys.stderr)

    at_risk = [
        {
            "decision_id": n.id,
            "title": n.title,
            "risk_score": score,
            "reasons": reasons,
            "last_reviewed": n.date if n.id in has_follow_up else None,
            "recommendation": recommendations.get(n.id, "Assign an owner to review this decision."),
        }
        for n, score, reasons in scored
    ]
    return {"at_risk": at_risk}


# ── 4. Decision Debt Score (pure SQL/graph aggregation, no LLM) ──────────────

def compute_debt_score(memory, user_id: Optional[str], scope: str = "all") -> dict:
    if not user_id:
        return {"debt_score": 0, "high_risk_count": 0, "total_decisions": 0, "top_offenders": []}

    nodes = _scoped_decisions(memory, user_id, scope, lookback_days=None)
    total = len(nodes)
    if total == 0:
        return {"debt_score": 0, "high_risk_count": 0, "total_decisions": 0, "top_offenders": []}

    follow_up_pairs = memory.graph.get_edges_by_type("follow_up", user_id=user_id)
    has_follow_up = {n.id for pair in follow_up_pairs for n in pair}

    offenders: list[tuple[DecisionNode, int, float]] = []
    high_risk = 0
    for n in nodes:
        if n.id in has_follow_up:
            continue
        days = _days_since(n.date)
        if days is None or days < 365:
            continue
        weight = 2.0 if _has_impact_keywords(n) else 1.0
        offenders.append((n, days, weight))
        if weight >= 2.0 or days > 730:
            high_risk += 1

    raw_debt = sum(w for _, _, w in offenders)
    debt_score = min(100, round((raw_debt / total) * 100))
    offenders.sort(key=lambda t: (t[2], t[1]), reverse=True)

    return {
        "debt_score": debt_score,
        "high_risk_count": high_risk,
        "total_decisions": total,
        "top_offenders": [n.id for n, _, _ in offenders[:10]],
    }
