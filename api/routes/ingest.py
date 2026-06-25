from fastapi import APIRouter, BackgroundTasks, Depends, Request
from pydantic import BaseModel
from api.auth import get_current_user, UserProfile

router = APIRouter()


class IngestRequest(BaseModel):
    sources: list[str] = ["slack", "gmail", "drive", "jira", "zoom"]
    lookback_days: int = 30


def get_orchestrator(request: Request):
    return request.app.state.orchestrator


@router.post("/ingest")
async def ingest(
    req: IngestRequest,
    background_tasks: BackgroundTasks,
    orchestrator=Depends(get_orchestrator),
    current_user: UserProfile = Depends(get_current_user),
):
    """Manually trigger a full ingestion run (runs in background)."""
    background_tasks.add_task(orchestrator.run_ingestion, current_user.uid)
    return {"status": "ingestion_started", "message": "Ingestion running in background"}
