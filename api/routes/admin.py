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

    # Real per-source counts + last-synced timestamps from the inventory table
    # (populated on every ingestion cycle, see core/orchestrator.py's
    # _synthesize) — previously these were a hardcoded date and a fraction of
    # total_decisions, i.e. fabricated numbers with no relationship to what
    # was actually fetched.
    item_counts = memory.inventory_counts(current_user.uid) if memory else {}
    last_synced = memory.inventory_last_synced(current_user.uid) if memory else {}
    frontend_to_inventory_source = {
        "slack": "Slack", "gmail": "Email", "drive": "Google Drive",
        "jira": "Jira", "zoom": "Zoom", "github": "GitHub",
    }

    connectors = []
    for name in ["slack", "gmail", "drive", "jira", "zoom", "github"]:
        connected = conn_statuses[name]
        source = frontend_to_inventory_source[name]
        connectors.append({
            "name": name,
            "connected": connected,
            "last_synced": last_synced.get(source) if connected else None,
            "total_items": item_counts.get(source, 0) if connected else 0,
        })

    return {
        "connectors": connectors,
        "total_decisions": stats.get("total_decisions", 0),
        "total_relations": stats.get("total_relations", 0),
    }


@router.get("/admin/mcp-activity")
async def mcp_activity(current_user: UserProfile = Depends(get_current_user)):
    """Real MCP tool-call history + stats for THIS user only (core/mcp_telemetry.py).
    Previously the dashboard's "Activity Monitor" panel rendered a hardcoded/
    simulated log — neither MCP transport persisted invocations anywhere
    queryable. Every call on both transports (mcp_server.py's stdio tools,
    api/routes/mcp_remote.py's tools/call) now writes here."""
    from core.mcp_telemetry import get_recent_calls, get_stats

    logs = get_recent_calls(current_user.uid, limit=20)
    stats = get_stats(current_user.uid)

    return {
        "logs": [
            {
                "id": str(row["id"]),
                "timestamp": row["created_at"],
                "client": row["client_name"] or "Unknown client",
                "tool": row["tool_name"],
                "transport": row["transport"],
                "status": row["status"],
            }
            for row in logs
        ],
        "stats": {
            "totalRequests": stats["total_requests"],
            "readOps": stats["read_ops"],
            "writeOps": stats["write_ops"],
            "activeClients": stats["active_clients"],
        },
    }
