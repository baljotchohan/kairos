from fastapi import APIRouter
from datetime import datetime

router = APIRouter()


@router.get("/health")
async def health():
    return {"status": "ok", "service": "kairos", "timestamp": datetime.utcnow().isoformat()}
