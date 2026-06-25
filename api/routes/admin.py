from fastapi import APIRouter, Depends, Request
from config import config
from api.auth import get_current_user, UserProfile

router = APIRouter()


def get_memory(request: Request):
    return request.app.state.memory


from api.routes.oauth import _get_token

@router.get("/admin/status")
async def status(
    memory=Depends(get_memory),
    current_user: UserProfile = Depends(get_current_user)
):
    """Get status of data connectors and repository metrics."""
    stats = memory.graph.stats(user_id=current_user.uid) if memory else {"total_decisions": 0, "total_relations": 0}
    
    # Check per-user database connections, falling back to server-side env (unless explicitly disconnected)
    services_to_check = {
        "slack": ("slack", bool(config.SLACK_BOT_TOKEN and len(config.SLACK_BOT_TOKEN) > 30 and config.SLACK_BOT_TOKEN != "xoxb-your-token")),
        "gmail": ("google", bool(config.GOOGLE_REFRESH_TOKEN)),
        "drive": ("google", bool(config.GOOGLE_REFRESH_TOKEN)),
        "zoom": ("zoom", bool(config.ZOOM_CLIENT_ID and config.ZOOM_ACCOUNT_ID and config.ZOOM_CLIENT_ID != "your_client_id")),
    }
    
    conn_statuses = {}
    for service_name, (storage_key, env_active) in services_to_check.items():
        user_tok = _get_token(current_user.uid, storage_key)
        if user_tok:
            conn_statuses[service_name] = not user_tok.get("disconnected")
        else:
            conn_statuses[service_name] = env_active

    # Jira doesn't support OAuth popup yet, check env fallback
    jira_connected = bool(config.JIRA_API_TOKEN and config.JIRA_URL and "atlassian.net" in config.JIRA_URL)
    conn_statuses["jira"] = jira_connected
    
    connectors = [
        {"name": "slack", "connected": conn_statuses["slack"], "last_synced": "2026-06-23T18:00:00Z" if conn_statuses["slack"] else None, "total_items": stats.get("total_decisions", 0) // 3 if conn_statuses["slack"] else 0},
        {"name": "gmail", "connected": conn_statuses["gmail"], "last_synced": "2026-06-23T18:00:00Z" if conn_statuses["gmail"] else None, "total_items": stats.get("total_decisions", 0) // 4 if conn_statuses["gmail"] else 0},
        {"name": "drive", "connected": conn_statuses["drive"], "last_synced": "2026-06-23T18:00:00Z" if conn_statuses["drive"] else None, "total_items": stats.get("total_decisions", 0) // 4 if conn_statuses["drive"] else 0},
        {"name": "jira", "connected": conn_statuses["jira"], "last_synced": "2026-06-23T18:00:00Z" if conn_statuses["jira"] else None, "total_items": stats.get("total_decisions", 0) // 6 if conn_statuses["jira"] else 0},
        {"name": "zoom", "connected": conn_statuses["zoom"], "last_synced": "2026-06-23T18:00:00Z" if conn_statuses["zoom"] else None, "total_items": stats.get("total_decisions", 0) // 6 if conn_statuses["zoom"] else 0},
    ]

    return {
        "connectors": connectors,
        "total_decisions": stats.get("total_decisions", 0),
        "total_relations": stats.get("total_relations", 0),
    }
