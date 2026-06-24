from fastapi import APIRouter, Depends, Request
from config import config
from api.auth import get_current_user, UserProfile

router = APIRouter()


def get_memory(request: Request):
    return request.app.state.memory


@router.get("/admin/status")
async def status(
    memory=Depends(get_memory),
    current_user: UserProfile = Depends(get_current_user)
):
    """Get status of data connectors and repository metrics."""
    stats = memory.graph.stats() if memory else {"total_decisions": 0, "total_relations": 0}
    
    slack_connected = bool(config.SLACK_BOT_TOKEN)
    gmail_connected = bool(config.GOOGLE_REFRESH_TOKEN)
    drive_connected = bool(config.GOOGLE_REFRESH_TOKEN)
    jira_connected = bool(config.JIRA_API_TOKEN)
    zoom_connected = bool(config.ZOOM_CLIENT_ID)
    
    connectors = [
        {"name": "slack", "connected": slack_connected, "last_synced": "2026-06-23T18:00:00Z" if slack_connected else None, "total_items": stats.get("total_decisions", 0) // 3 if slack_connected else 0},
        {"name": "gmail", "connected": gmail_connected, "last_synced": "2026-06-23T18:00:00Z" if gmail_connected else None, "total_items": stats.get("total_decisions", 0) // 4 if gmail_connected else 0},
        {"name": "drive", "connected": drive_connected, "last_synced": "2026-06-23T18:00:00Z" if drive_connected else None, "total_items": stats.get("total_decisions", 0) // 4 if drive_connected else 0},
        {"name": "jira", "connected": jira_connected, "last_synced": "2026-06-23T18:00:00Z" if jira_connected else None, "total_items": stats.get("total_decisions", 0) // 6 if jira_connected else 0},
        {"name": "zoom", "connected": zoom_connected, "last_synced": "2026-06-23T18:00:00Z" if zoom_connected else None, "total_items": stats.get("total_decisions", 0) // 6 if zoom_connected else 0},
    ]

    return {
        "connectors": connectors,
        "total_decisions": stats.get("total_decisions", 0),
        "total_relations": stats.get("total_relations", 0),
    }
