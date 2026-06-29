from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel

from api.auth import get_current_user, UserProfile
from core.graph import DecisionNode

router = APIRouter()


# ── Dependency ─────────────────────────────────────────────────────────────────

def get_memory(request: Request):
    return request.app.state.memory


# ── Models ────────────────────────────────────────────────────────────────────

class StoreRequest(BaseModel):
    title: str
    summary: str
    date: str
    source: str
    source_url: str = ""
    topics: list[str] = []
    participants: list[str] = []
    outcome: str = ""
    context: str = ""
    alternatives: list[str] = []
    decision_maker: str = ""


# ── Decisions ─────────────────────────────────────────────────────────────────

@router.get("/decisions")
async def list_decisions(
    limit: int = 100,
    offset: int = 0,
    memory=Depends(get_memory),
    current_user: UserProfile = Depends(get_current_user),
):
    """List this user's decisions (paginated, newest first)."""
    limit = max(1, min(limit, 500))   # clamp to a sane bound
    offset = max(0, offset)
    nodes = memory.graph.all_decisions(user_id=current_user.uid)
    nodes.sort(key=lambda n: n.date or "", reverse=True)
    page = nodes[offset:offset + limit]
    return {
        "total": len(nodes),
        "limit": limit,
        "offset": offset,
        "decisions": [
            {
                "id": n.id,
                "title": n.title,
                "summary": n.summary,
                "date": n.date,
                "source": n.source,
                "topics": n.topics,
                "participants": n.participants,
            }
            for n in page
        ],
    }


@router.get("/decisions/search")
async def search_decisions(
    q: Optional[str] = None,
    topic: Optional[str] = None,
    person: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    memory=Depends(get_memory),
    current_user: UserProfile = Depends(get_current_user),
):
    """
    Semantic search (q=) or structured search (topic, person, date_from, date_to).
    Both can be combined.
    """
    results = []

    if q:
        semantic = memory.semantic_search(q, n_results=10, user_id=current_user.uid)
        results.extend(semantic)

    if topic or person or date_from or date_to:
        structured = memory.structured_search(
            topic=topic, person=person,
            date_from=date_from, date_to=date_to,
            user_id=current_user.uid
        )
        # Merge, avoid duplicates
        existing_ids = {n.id for n in results}
        results.extend(n for n in structured if n.id not in existing_ids)

    return {
        "query": {"q": q, "topic": topic, "person": person},
        "total": len(results),
        "decisions": [
            {
                "id": n.id,
                "title": n.title,
                "summary": n.summary,
                "date": n.date,
                "source": n.source,
                "source_url": n.source_url,
                "topics": n.topics,
                "participants": n.participants,
                "outcome": n.outcome,
                "metadata": n.metadata,
            }
            for n in results
        ],
    }


@router.get("/decisions/{decision_id}")
async def get_decision(decision_id: str, memory=Depends(get_memory), current_user: UserProfile = Depends(get_current_user)):
    """Get a single decision with all related decisions."""
    node = memory.graph.get_decision(decision_id, user_id=current_user.uid)
    if not node:
        raise HTTPException(status_code=404, detail="Decision not found")

    related = memory.graph.get_connected(decision_id, depth=2, user_id=current_user.uid)

    return {
        "id": node.id,
        "title": node.title,
        "summary": node.summary,
        "date": node.date,
        "source": node.source,
        "source_url": node.source_url,
        "topics": node.topics,
        "participants": node.participants,
        "outcome": node.outcome,
        "metadata": node.metadata,
        "related": [
            {"id": r.id, "title": r.title, "date": r.date, "source": r.source}
            for r in related
        ],
    }


# ── Manual store ──────────────────────────────────────────────────────────────

@router.post("/store")
async def store_decision(body: StoreRequest, memory=Depends(get_memory), current_user: UserProfile = Depends(get_current_user)):
    """Manually store a decision (from MCP tool or API call)."""
    node = DecisionNode(
        id=memory.make_id(),
        title=body.title,
        summary=body.summary,
        date=body.date,
        participants=body.participants,
        source=body.source,
        source_url=body.source_url,
        topics=body.topics,
        outcome=body.outcome,
        raw_text="",
        metadata={
            "context": body.context,
            "alternatives": body.alternatives,
            "decision_maker": body.decision_maker,
        },
        user_id=current_user.uid,
    )
    memory.store(node, user_id=current_user.uid)
    return {"status": "stored", "id": node.id, "title": node.title}


# ── Graph ─────────────────────────────────────────────────────────────────────

@router.get("/graph/stats")
async def graph_stats(memory=Depends(get_memory), current_user: UserProfile = Depends(get_current_user)):
    """Decision graph statistics."""
    stats = memory.graph.stats(user_id=current_user.uid)
    return stats


@router.post("/graph/export/obsidian")
async def export_obsidian(memory=Depends(get_memory), current_user: UserProfile = Depends(get_current_user)):
    """Export/refresh the Obsidian vault."""
    if current_user.is_anonymous:
        raise HTTPException(status_code=403, detail="Anonymous guests cannot export vaults")
    memory.rebuild_obsidian(user_id=current_user.uid)
    vault_folder = f"KAIROS_{current_user.uid}"
    return {"status": "exported", "vault": f"{memory.obsidian_vault}/{vault_folder}"}
