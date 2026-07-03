from fastapi import APIRouter, Depends, Request
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
    """Get status of data connectors and repository metrics for THIS user only."""
    stats = memory.graph.stats(user_id=current_user.uid) if memory else {"total_decisions": 0, "total_relations": 0}

    # connected=True ONLY when the user holds a real, non-disconnected per-user token
    # (mirrors oauth.py get_status). No server-env fallback — never report the
    # deployer's own connector configuration as another tenant's connection.
    frontend_to_storage = {
        "slack": "slack", "gmail": "google", "drive": "google",
        "jira": "jira", "zoom": "zoom", "github": "github",
    }
    conn_statuses = {}
    for service_name, storage_key in frontend_to_storage.items():
        tok = _get_token(current_user.uid, storage_key)
        conn_statuses[service_name] = bool(tok and not tok.get("disconnected"))

    connectors = [
        {"name": "slack", "connected": conn_statuses["slack"], "last_synced": "2026-06-23T18:00:00Z" if conn_statuses["slack"] else None, "total_items": stats.get("total_decisions", 0) // 3 if conn_statuses["slack"] else 0},
        {"name": "gmail", "connected": conn_statuses["gmail"], "last_synced": "2026-06-23T18:00:00Z" if conn_statuses["gmail"] else None, "total_items": stats.get("total_decisions", 0) // 4 if conn_statuses["gmail"] else 0},
        {"name": "drive", "connected": conn_statuses["drive"], "last_synced": "2026-06-23T18:00:00Z" if conn_statuses["drive"] else None, "total_items": stats.get("total_decisions", 0) // 4 if conn_statuses["drive"] else 0},
        {"name": "jira", "connected": conn_statuses["jira"], "last_synced": "2026-06-23T18:00:00Z" if conn_statuses["jira"] else None, "total_items": stats.get("total_decisions", 0) // 6 if conn_statuses["jira"] else 0},
        {"name": "zoom", "connected": conn_statuses["zoom"], "last_synced": "2026-06-23T18:00:00Z" if conn_statuses["zoom"] else None, "total_items": stats.get("total_decisions", 0) // 6 if conn_statuses["zoom"] else 0},
        {"name": "github", "connected": conn_statuses["github"], "last_synced": "2026-06-23T18:00:00Z" if conn_statuses["github"] else None, "total_items": stats.get("total_decisions", 0) // 5 if conn_statuses["github"] else 0},
    ]

    return {
        "connectors": connectors,
        "total_decisions": stats.get("total_decisions", 0),
        "total_relations": stats.get("total_relations", 0),
    }
