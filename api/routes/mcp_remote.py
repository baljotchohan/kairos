"""
KAIROS Remote MCP — multi-tenant Streamable-HTTP MCP server.

One deployed endpoint serves every user, scoped to their own data via a signed
per-user token embedded in the URL:

    POST  https://<backend>/mcp/u/<token>     ← MCP JSON-RPC (Streamable HTTP)

A user adds this single URL as a custom connector in Claude Desktop, Claude
web/mobile, ChatGPT, or Cursor. Every JSON-RPC call resolves the token → user_id
and scopes the three KAIROS tools (get_context / store_context / search_decisions)
to that user's organizational memory — no cross-user leakage.

This is a minimal, spec-compliant Streamable-HTTP implementation (JSON-RPC 2.0
over HTTP POST, JSON responses) because the pinned `mcp` lib is too old to mount
its own Streamable-HTTP ASGI app. The stdio server (mcp_server.py) is unchanged.

Auth model: the token in the URL IS the credential (bearer-in-URL). Pragmatic and
one-click; the documented upgrade is OAuth 2.1 + dynamic client registration
(docs/REMOTE_MCP.md).
"""

from __future__ import annotations

import uuid
import logging

from fastapi import APIRouter, Request, Depends
from fastapi.responses import JSONResponse

from core.graph import DecisionNode
from core.mcp_auth import verify_mcp_token, mint_mcp_token
from config import config
from api.auth import get_current_user, UserProfile

log = logging.getLogger(__name__)

PROTOCOL_VERSION = "2025-03-26"

# ── Tool definitions (advertised via tools/list) ───────────────────────────────

TOOLS = [
    {
        "name": "get_context",
        "description": (
            "Get organizational context and decisions relevant to a query. Call this "
            "before answering ANY question about company decisions, history, architecture, "
            "vendors, or strategy. Returns the most relevant past decisions with context, "
            "sources, participants, and outcomes."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Natural-language question."},
                "limit": {"type": "integer", "description": "Max decisions to return.", "default": 5},
            },
            "required": ["query"],
        },
    },
    {
        "name": "store_context",
        "description": (
            "Store an important decision or organizational context permanently in KAIROS. "
            "Call this whenever the user shares a decision worth remembering. Auto-links to "
            "related decisions in the graph."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "decision": {"type": "string", "description": "Short decision title."},
                "context": {"type": "string", "description": "Full context / why / trade-offs."},
                "participants": {"type": "array", "items": {"type": "string"}, "default": []},
                "date": {"type": "string", "description": "ISO date YYYY-MM-DD."},
                "source": {"type": "string", "description": "Where this came from."},
                "project": {"type": "string", "default": "General"},
            },
            "required": ["decision", "context", "date", "source"],
        },
    },
    {
        "name": "search_decisions",
        "description": (
            "Search decisions by topic, date range, person, or project. Use for precise "
            "filtered queries; prefer get_context for open-ended 'why do we...' questions."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "topic": {"type": "string"},
                "date_from": {"type": "string"},
                "date_to": {"type": "string"},
                "person": {"type": "string"},
                "project": {"type": "string"},
            },
            "required": ["topic"],
        },
    },
]


# ── Tool implementations (always scoped to the resolved user_id) ────────────────

def _tool_get_context(memory, user_id: str, query: str, limit: int = 5) -> str:
    results = memory.get_context(query, n_results=limit, user_id=user_id)
    if not results:
        return (
            f"KAIROS: No decisions found in organizational memory for: '{query}'. "
            "This topic has no recorded history yet."
        )
    lines = [f"KAIROS ORGANIZATIONAL MEMORY — {len(results)} decision(s) for: '{query}'", "=" * 60]
    for i, d in enumerate(results, 1):
        participants = ", ".join(d["participants"]) if d["participants"] else "Unknown"
        lines.append(
            f"\nDECISION {i}: {d['title']}\n  Date: {d['date']}\n  Source: {d['source']}\n"
            f"  Participants: {participants}\n  Summary: {d['summary']}\n  Outcome: {d['outcome']}\n"
            f"  Related: {len(d.get('related', []))} connected decision(s)"
        )
    return "\n".join(lines)


def _tool_store_context(memory, user_id: str, decision: str, context: str,
                        date: str, source: str, participants=None, project: str = "General") -> str:
    participants = participants or []
    node = DecisionNode(
        id=str(uuid.uuid4()),
        title=decision,
        summary=context[:300],
        date=date,
        participants=participants,
        source=source,
        source_url="",
        topics=[project] if project != "General" else [],
        outcome=context[:500],
        raw_text=context,
        metadata={"project": project, "stored_via": "mcp_remote"},
        user_id=user_id,
    )
    memory.store(node, user_id=user_id)
    return (
        f"KAIROS: Decision stored.\n  ID: {node.id}\n  Title: {decision}\n  Date: {date}\n"
        f"  Source: {source}\n  Project: {project}\nAuto-linked to related decisions."
    )


def _tool_search_decisions(memory, user_id: str, topic: str, date_from=None,
                          date_to=None, person=None, project=None) -> str:
    results = memory.structured_search(
        topic=topic or project, person=person,
        date_from=date_from, date_to=date_to, user_id=user_id,
    )
    if not results:
        return f"KAIROS: No decisions found matching topic='{topic}'."
    lines = [f"KAIROS: {len(results)} decision(s) found", "=" * 60]
    for i, n in enumerate(results, 1):
        participants = ", ".join(n.participants) if n.participants else "Unknown"
        lines.append(
            f"\n{i}. [{n.date}] {n.title}\n   Source: {n.source}\n   Participants: {participants}\n"
            f"   Summary: {n.summary}"
        )
    return "\n".join(lines)


def _call_tool(memory, user_id: str, name: str, args: dict) -> str:
    if name == "get_context":
        return _tool_get_context(memory, user_id, args.get("query", ""), int(args.get("limit", 5)))
    if name == "store_context":
        return _tool_store_context(
            memory, user_id, args.get("decision", ""), args.get("context", ""),
            args.get("date", ""), args.get("source", ""),
            args.get("participants", []), args.get("project", "General"),
        )
    if name == "search_decisions":
        return _tool_search_decisions(
            memory, user_id, args.get("topic", ""), args.get("date_from"),
            args.get("date_to"), args.get("person"), args.get("project"),
        )
    raise ValueError(f"Unknown tool: {name}")


# ── JSON-RPC dispatch ───────────────────────────────────────────────────────────

def _result(req_id, result):
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _error(req_id, code, message):
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


def _handle_message(msg: dict, memory, user_id: str):
    """Process one JSON-RPC message. Returns a response dict, or None for notifications."""
    method = msg.get("method")
    req_id = msg.get("id")
    params = msg.get("params") or {}

    # Notifications (no id) — acknowledge with no response body.
    if req_id is None:
        return None

    if method == "initialize":
        return _result(req_id, {
            "protocolVersion": params.get("protocolVersion", PROTOCOL_VERSION),
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "KAIROS", "version": "1.0.0"},
            "instructions": (
                "KAIROS is your company's organizational memory. Call get_context before "
                "answering questions about past company decisions; call store_context to "
                "permanently remember new decisions."
            ),
        })
    if method == "ping":
        return _result(req_id, {})
    if method == "tools/list":
        return _result(req_id, {"tools": TOOLS})
    if method == "tools/call":
        name = params.get("name")
        args = params.get("arguments") or {}
        try:
            text = _call_tool(memory, user_id, name, args)
            return _result(req_id, {"content": [{"type": "text", "text": text}], "isError": False})
        except Exception as e:
            log.warning("MCP tool '%s' failed for %s", name, user_id, exc_info=True)
            return _result(req_id, {"content": [{"type": "text", "text": f"Tool error: {e}"}], "isError": True})

    return _error(req_id, -32601, f"Method not found: {method}")


# ── Routers ─────────────────────────────────────────────────────────────────────

# (1) The MCP transport endpoint — mounted at the app root for a clean URL.
mcp_rpc_router = APIRouter()


@mcp_rpc_router.post("/mcp/u/{token}")
async def mcp_streamable_http(token: str, request: Request):
    user_id = verify_mcp_token(token)
    if not user_id:
        return JSONResponse(
            {"jsonrpc": "2.0", "id": None,
             "error": {"code": -32001, "message": "Invalid or revoked KAIROS connect token."}},
            status_code=401,
        )

    memory = request.app.state.memory
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(_error(None, -32700, "Parse error"), status_code=400)

    # JSON-RPC supports single messages and batches (a JSON array).
    if isinstance(body, list):
        responses = [r for r in (_handle_message(m, memory, user_id) for m in body) if r is not None]
        return JSONResponse(responses) if responses else JSONResponse([], status_code=202)

    resp = _handle_message(body, memory, user_id)
    if resp is None:
        # Notification — nothing to return.
        return JSONResponse({}, status_code=202)
    return JSONResponse(resp)


@mcp_rpc_router.get("/mcp/u/{token}")
async def mcp_streamable_http_get(token: str):
    # GET opens an optional server→client SSE stream. KAIROS pushes no unsolicited
    # messages, so we signal "no stream" — clients fall back to POST request/response.
    if not verify_mcp_token(token):
        return JSONResponse({"error": "invalid token"}, status_code=401)
    return JSONResponse({"detail": "This MCP server is request/response only (POST)."}, status_code=405)


# (2) The connect-info endpoint — authed, mounted under /api.
mcp_connect_router = APIRouter(prefix="/mcp", tags=["mcp"])


@mcp_connect_router.get("/connection")
def mcp_connection_info(current_user: UserProfile = Depends(get_current_user)):
    """Return this user's personal remote-MCP connect URL + ready-to-paste configs."""
    token = mint_mcp_token(current_user.uid)
    url = f"{config.BACKEND_URL.rstrip('/')}/mcp/u/{token}"
    return {
        "url": url,
        "token": token,
        "tools": [t["name"] for t in TOOLS],
        "claude_desktop_config": {"mcpServers": {"kairos": {"url": url}}},
        "cursor_config": {"mcpServers": {"kairos": {"url": url}}},
        "instructions": {
            "claude_web_mobile": "Settings → Connectors → Add custom connector → paste the URL.",
            "chatgpt": "Settings → Connectors (developer mode) → Add → paste the URL.",
            "claude_desktop": "Paste claude_desktop_config into claude_desktop_config.json.",
        },
    }
