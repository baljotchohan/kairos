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

import json
import uuid
import logging

import asyncio
from fastapi import APIRouter, Request, Depends
from fastapi.responses import JSONResponse, Response, StreamingResponse

# Registry for active MCP SSE transport sessions (mapping session_id -> asyncio.Queue)
_active_sessions: dict[str, asyncio.Queue] = {}

from core.graph import DecisionNode
from core.mcp_auth import verify_mcp_token, mint_mcp_token
from config import config
from api.auth import get_current_user, UserProfile

log = logging.getLogger(__name__)

PROTOCOL_VERSION = "2025-03-26"

# KAIROS brand logo (the node-constellation "K") served at /mcp/icon.svg and
# advertised in serverInfo.icons so Claude/connector UIs show the real logo
# instead of a placeholder.
KAIROS_ICON_SVG = """<svg width="512" height="512" viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg">
  <rect width="100" height="100" rx="0" fill="#171717"/>
  <defs>
    <radialGradient id="n" cx="38%" cy="32%" r="65%">
      <stop offset="0%" stop-color="#d8b4fe"/>
      <stop offset="40%" stop-color="#a855f7"/>
      <stop offset="100%" stop-color="#7e22ce"/>
    </radialGradient>
    <radialGradient id="s" cx="40%" cy="30%" r="50%">
      <stop offset="0%" stop-color="#fff" stop-opacity="0.35"/>
      <stop offset="100%" stop-color="#fff" stop-opacity="0"/>
    </radialGradient>
    <linearGradient id="e" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#c084fc"/>
      <stop offset="100%" stop-color="#7c3aed"/>
    </linearGradient>
  </defs>
  <g stroke="url(#e)" stroke-width="3.5" stroke-linecap="round" opacity="0.85">
    <line x1="28" y1="18" x2="28" y2="50"/>
    <line x1="28" y1="50" x2="28" y2="82"/>
    <line x1="28" y1="50" x2="48" y2="50"/>
    <line x1="48" y1="50" x2="63" y2="35"/>
    <line x1="63" y1="35" x2="78" y2="18"/>
    <line x1="48" y1="50" x2="63" y2="65"/>
    <line x1="63" y1="65" x2="78" y2="82"/>
  </g>
  <g>
    <circle cx="28" cy="18" r="7" fill="url(#n)"/><circle cx="28" cy="18" r="7" fill="url(#s)"/>
    <circle cx="28" cy="50" r="7" fill="url(#n)"/><circle cx="28" cy="50" r="7" fill="url(#s)"/>
    <circle cx="28" cy="82" r="7" fill="url(#n)"/><circle cx="28" cy="82" r="7" fill="url(#s)"/>
    <circle cx="48" cy="50" r="7" fill="url(#n)"/><circle cx="48" cy="50" r="7" fill="url(#s)"/>
    <circle cx="63" cy="35" r="7" fill="url(#n)"/><circle cx="63" cy="35" r="7" fill="url(#s)"/>
    <circle cx="78" cy="18" r="7" fill="url(#n)"/><circle cx="78" cy="18" r="7" fill="url(#s)"/>
    <circle cx="63" cy="65" r="7" fill="url(#n)"/><circle cx="63" cy="65" r="7" fill="url(#s)"/>
    <circle cx="78" cy="82" r="7" fill="url(#n)"/><circle cx="78" cy="82" r="7" fill="url(#s)"/>
  </g>
</svg>"""

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
        },
    },
]


# ── Tool implementations (always scoped to the resolved user_id) ────────────────

def _tool_get_context(memory, user_id: str, query: str, limit: int = 5) -> str:
    # Hybrid retrieval (vector + keyword + source-aware + graph neighbours) — the
    # SAME rich recall the KAIROS web app uses, so Claude actually finds what's in
    # memory instead of vector-only near-misses.
    nodes = memory.hybrid_search(query, n_results=limit, user_id=user_id)
    if not nodes:
        return (
            f"KAIROS: No decisions found in organizational memory for: '{query}'. "
            "This topic has no recorded history yet."
        )
    lines = [f"KAIROS ORGANIZATIONAL MEMORY — {len(nodes)} decision(s) for: '{query}'", "=" * 60]
    for i, n in enumerate(nodes, 1):
        participants = ", ".join(n.participants) if n.participants else "Unknown"
        related = memory.graph.get_connected(n.id, depth=1, user_id=user_id)
        ctx = (n.metadata or {}).get("context", "")
        lines.append(
            f"\nDECISION {i}: {n.title}\n  Date: {n.date}\n  Source: {n.source} — {n.source_url}\n"
            f"  Participants: {participants}\n  Summary: {n.summary}\n"
            + (f"  Context: {ctx}\n" if ctx else "")
            + f"  Outcome: {n.outcome}\n  Related: {len(related)} connected decision(s)"
        )
    return "\n".join(lines)


def _tool_store_context(memory, user_id: str, decision: str, context: str,
                        date: str, source: str, participants=None, project: str = "General") -> str:
    if participants is None:
        participants = []
    elif isinstance(participants, str):
        participants = [participants]
    else:
        participants = [p for p in participants if p is not None]

    if project is None:
        project = "General"

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


def _tool_search_decisions(memory, user_id: str, topic=None, date_from=None,
                          date_to=None, person=None, project=None) -> str:
    if not topic and not project and not person and not date_from and not date_to:
        return "KAIROS: Please provide at least one search filter (topic, person, project, date range)."

    # Use project as an additional topic filter if provided
    search_topic = topic
    if project and not topic:
        search_topic = project
    elif project and topic:
        search_topic = topic  # topic takes priority; project is secondary

    results = memory.structured_search(
        topic=search_topic, person=person,
        date_from=date_from, date_to=date_to, user_id=user_id,
    )

    # Secondary filter by project if topic was also set
    if project and topic:
        project_results = memory.structured_search(
            topic=project, person=person,
            date_from=date_from, date_to=date_to, user_id=user_id,
        )
        seen = {n.id for n in results}
        for n in project_results:
            if n.id not in seen:
                results.append(n)
                seen.add(n.id)

    # Fall back to hybrid semantic recall when the exact filters matched nothing,
    # so a near-miss topic still surfaces related decisions.
    if not results and search_topic:
        results = memory.hybrid_search(search_topic, n_results=8, user_id=user_id)

    if not results:
        return "KAIROS: No decisions found matching filters."

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
        icon_url = f"{config.BACKEND_URL.rstrip('/')}/mcp/icon.svg"
        return _result(req_id, {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {
                "name": "KAIROS",
                "title": "KAIROS — Organizational Memory",
                "version": "1.0.0",
                "websiteUrl": config.FRONTEND_URL,
                # MCP icon advertisement so connector UIs show the real logo.
                "icons": [
                    {"src": icon_url, "mimeType": "image/svg+xml", "sizes": "any"},
                ],
            },
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


@mcp_rpc_router.get("/mcp/icon.svg")
def mcp_icon():
    """Public KAIROS logo for MCP connector UIs (referenced from serverInfo.icons)."""
    return Response(
        content=KAIROS_ICON_SVG,
        media_type="image/svg+xml",
        headers={"Cache-Control": "public, max-age=86400"},
    )


def _format_response(payload, extra_headers: dict | None = None):
    """Return the JSON-RPC response as plain JSON.

    Per the MCP Streamable-HTTP spec, the server may respond with either
    application/json or text/event-stream.  Plain JSON is more compatible across
    all MCP clients (Claude web/mobile, Claude Desktop, Cursor, ChatGPT) for
    synchronous tool responses.  We never need SSE here because none of our tools
    stream — every response is computed synchronously and returned whole."""
    headers = dict(extra_headers or {})
    return JSONResponse(payload, headers=headers)


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

    # Pure stateless Streamable-HTTP: respond directly to every POST.
    # No persistent SSE session routing — each request gets an immediate JSON response.
    # This is the most compatible approach for Claude web/mobile, Claude Desktop,
    # Cursor and ChatGPT custom connectors.
    if isinstance(body, list):
        responses = [r for m in body if (r := _handle_message(m, memory, user_id)) is not None]
        if not responses:
            return Response(status_code=202)
        return _format_response(responses)

    extra_headers = {}
    if body.get("method") == "initialize":
        extra_headers["Mcp-Session-Id"] = uuid.uuid4().hex

    resp = _handle_message(body, memory, user_id)
    if resp is None:
        return Response(status_code=202)

    return _format_response(resp, extra_headers)


@mcp_rpc_router.get("/mcp/u/{token}")
async def mcp_streamable_http_get(token: str, request: Request):
    # GET establishes the SSE channel for official MCP HTTP/SSE clients (like Claude).
    # Returns 200 OK and pushes the 'endpoint' event containing the POST URL.
    user_id = verify_mcp_token(token)
    if not user_id:
        return JSONResponse({"error": "invalid token"}, status_code=401)

    session_id = uuid.uuid4().hex
    queue = asyncio.Queue()
    _active_sessions[session_id] = queue

    async def sse_generator():
        # Push the endpoint configuration event immediately
        scheme = request.headers.get("x-forwarded-proto", request.url.scheme)
        host = request.headers.get("x-forwarded-host", request.url.netloc)
        base_url = f"{scheme}://{host}"
        endpoint_url = f"{base_url}/mcp/u/{token}?session_id={session_id}"
        yield f"event: endpoint\ndata: {endpoint_url}\n\n"

        if getattr(request.app.state, "testing", False):
            return

        try:
            while True:
                try:
                    # Wait for outgoing message responses with a timeout for keepalive
                    msg = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield f"event: message\ndata: {json.dumps(msg)}\n\n"
                except asyncio.TimeoutError:
                    # Keep-alive comment to keep connection active
                    yield ": ping\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            _active_sessions.pop(session_id, None)

    return StreamingResponse(
        sse_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive"
        }
    )


# No /.well-known/oauth-protected-resource endpoint — our auth is a signed token
# embedded in the URL path (/mcp/u/{token}), not a Bearer header. Serving that
# endpoint would cause Claude/ChatGPT to launch an OAuth flow that can never succeed.


# (2) The connect-info endpoint — authed, mounted under /api.
mcp_connect_router = APIRouter(prefix="/mcp", tags=["mcp"])


@mcp_connect_router.get("/connection")
def mcp_connection_info(request: Request, current_user: UserProfile = Depends(get_current_user)):
    """Return this user's personal remote-MCP connect URL + ready-to-paste configs."""
    token = mint_mcp_token(current_user.uid)
    scheme = request.headers.get("x-forwarded-proto", request.url.scheme)
    host = request.headers.get("x-forwarded-host", request.url.netloc)
    base_url = f"{scheme}://{host}"
    url = f"{base_url}/mcp/u/{token}"
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
