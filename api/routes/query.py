import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from api.auth import get_current_user, UserProfile

log = logging.getLogger(__name__)

router = APIRouter()


class QueryRequest(BaseModel):
    question: str
    user_role: str = "admin"  # admin | manager | employee
    session_id: str | None = None


class QueryResponse(BaseModel):
    answer: str
    sources: list[dict]
    decision_ids: list[str]


def get_orchestrator(request: Request):
    return request.app.state.orchestrator


@router.post("/query", response_model=QueryResponse)
async def query(
    req: QueryRequest,
    orchestrator=Depends(get_orchestrator),
    current_user: UserProfile = Depends(get_current_user)
):
    """Answer a natural language question using KAIROS memory."""
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    try:
        result = await orchestrator.query_with_memory(
            question=req.question,
            user_id=current_user.uid,
            session_id=req.session_id
        )
    except Exception:
        log.error("REST /query failed for user %s", current_user.uid, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Something went wrong while processing your question. Please try again.",
        )

    sources = result.get("sources", [])
    decision_ids = [s.get("id") for s in sources if s.get("id")]
    
    return QueryResponse(
        answer=result.get("answer", ""),
        sources=sources,
        decision_ids=decision_ids
    )
