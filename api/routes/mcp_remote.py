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

# Registry for active MCP SSE transport sessions: session_id -> (owner_user_id, queue).
# The owner is recorded at session creation (GET, one token per session) and checked
# on every POST before routing a response into it — without this, a POST authenticated
# as user A but supplying user B's session_id would deliver A's tool-call response into
# B's SSE stream (a cross-session response-injection bug, not a data-exfiltration one,
# since tool execution itself is separately scoped to the POST's own verified user_id —
# but injecting unrequested content into another user's trusted MCP stream is still a
# real integrity issue worth closing).
_active_sessions: dict[str, tuple[str, asyncio.Queue]] = {}


def _owned_session_queue(session_id: str | None, user_id: str) -> asyncio.Queue | None:
    """Return the SSE queue for session_id ONLY if it's owned by user_id."""
    if not session_id:
        return None
    entry = _active_sessions.get(session_id)
    if entry is None:
        return None
    owner_user_id, queue = entry
    if owner_user_id != user_id:
        log.warning("MCP SSE session %s owned by a different user — refusing to route response into it", session_id)
        return None
    return queue

from core.graph import DecisionNode
from core.mcp_auth import verify_mcp_token, mint_mcp_token, revoke_mcp_tokens
from core import decision_intelligence as di
from config import config
from api.auth import get_current_user, UserProfile

log = logging.getLogger(__name__)

PROTOCOL_VERSION = "2024-11-05"

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
                "query": {"type": "string", "description": "Natural-language question to query memory with."},
                "limit": {"type": "integer", "description": "Max decisions to return in search results.", "default": 5},
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
                "decision": {"type": "string", "description": "Short, clear title of the decision."},
                "context": {"type": "string", "description": "Full background context, rationale, and trade-offs of the decision."},
                "participants": {"type": "array", "items": {"type": "string"}, "description": "List of names of people involved in the decision.", "default": []},
                "date": {"type": "string", "description": "ISO format date of the decision (YYYY-MM-DD)."},
                "source": {"type": "string", "description": "Source of this information (e.g. Slack channel, meeting minutes, email)."},
                "project": {"type": "string", "description": "Associated project name or category.", "default": "General"},
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
                "topic": {"type": "string", "description": "Topic or keyword filter."},
                "date_from": {"type": "string", "description": "Start date for filtering decisions (YYYY-MM-DD)."},
                "date_to": {"type": "string", "description": "End date for filtering decisions (YYYY-MM-DD)."},
                "person": {"type": "string", "description": "Name of a participant to filter by."},
                "project": {"type": "string", "description": "Name of the project to filter by."},
            },
        },
    },
    {
        "name": "find_similar_decisions",
        "description": (
            "Check whether a new situation has genuine precedent in past decisions. Runs semantic "
            "search then has the model separate real precedent from topically-similar noise. Use "
            "before repeating a project/approach to find out if the company already tried something like it."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Describe the new situation, e.g. 'building a mobile app'."},
                "limit": {"type": "integer", "description": "Max genuine precedents to return.", "default": 5},
            },
            "required": ["query"],
        },
    },
    {
        "name": "detect_decision_patterns",
        "description": (
            "Proactively scan organizational memory for risky decision patterns: contradictory "
            "outcomes on the same topic, unreviewed vendor/contract spend, and bus-factor risk "
            "(one person as sole decision-maker across many high-impact calls)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "scope": {"type": "string", "description": "\"all\" or a specific topic/project name.", "default": "all"},
                "lookback_days": {"type": "integer", "description": "Only consider decisions within this many days.", "default": 365},
            },
        },
    },
    {
        "name": "predict_decision_risk",
        "description": (
            "Score decisions by risk of being stale, unowned, or overdue for review. Returns a "
            "0-100 risk score, reasons, and a recommendation per decision."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "decision_id": {"type": "string", "description": "If given, score only this one decision."},
                "scope": {"type": "string", "description": "\"all\" or a specific topic/project name.", "default": "all"},
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

    from core.memory import KairosMemory
    node_id = KairosMemory.make_id(title=decision, user_id=user_id)
    node = DecisionNode(
        id=node_id,
        title=decision,
        summary=decision,
        outcome=context,
        date=date or "",
        source=source or "MCP",
        source_url="",
        participants=participants,
        topics=[project] if project else [],
        user_id=user_id,
        metadata={"context": context, "project": project},
    )
    memory.store(node, user_id=user_id)

    return f"Successfully stored decision permanently in KAIROS memory (ID: {node.id})."


def _tool_search_decisions(memory, user_id: str, topic: str = None, date_from: str = None,
                           date_to: str = None, person: str = None, project: str = None) -> str:
    # Use the real KairosMemory API — structured_search supports topic, person, date range.
    nodes = memory.structured_search(
        topic=topic,
        date_from=date_from,
        date_to=date_to,
        person=person,
        user_id=user_id,
    )
    # Client-side project filter (structured_search doesn't have a project column filter)
    if project:
        nodes = [n for n in nodes if getattr(n, "project", None) == project]

    if not nodes:
        return "KAIROS: No decisions found matching the specified search filters."
    
    lines = [f"KAIROS: Found {len(nodes)} decision(s) matching search criteria:", "=" * 60]
    for i, n in enumerate(nodes, 1):
        participants = ", ".join(n.participants) if n.participants else "Unknown"
        lines.append(
            f"\nDECISION {i}: {n.title}\n  Date: {n.date}\n  Source: {n.source}\n"
            f"  Participants: {participants}\n  Summary: {n.summary}\n  Outcome: {n.outcome}"
        )
    return "\n".join(lines)


def _format_similar_decisions(result: dict) -> str:
    if not result["matches"]:
        return f"KAIROS: {result['verdict']}"
    lines = [f"KAIROS VERDICT: {result['verdict']}", "=" * 60]
    for i, m in enumerate(result["matches"], 1):
        lines.append(
            f"\n{i}. [{m['date']}] {m['title']} (similarity {m['similarity_score']:.0%})\n"
            f"   Summary: {m['summary']}\n   Outcome: {m['outcome']}\n"
            f"   Source:  {m['source_url'] or 'n/a'}"
        )
    return "\n".join(lines)


def _format_decision_patterns(result: dict) -> str:
    if not result["patterns"]:
        return "KAIROS: No risky decision patterns detected in the current scope."
    lines = [f"KAIROS: {len(result['patterns'])} pattern(s) detected", "=" * 60]
    for i, p in enumerate(result["patterns"], 1):
        lines.append(
            f"\n{i}. [{p['severity'].upper()}] {p['pattern_type'].replace('_', ' ')}\n"
            f"   {p['description']}\n   Affected: {len(p['affected_decisions'])} decision(s)\n"
            f"   Recommendation: {p['recommendation']}"
        )
    return "\n".join(lines)


def _format_decision_risk(result: dict) -> str:
    if not result["at_risk"]:
        return "KAIROS: No at-risk decisions found in the current scope."
    lines = [f"KAIROS: {len(result['at_risk'])} at-risk decision(s)", "=" * 60]
    for i, r in enumerate(result["at_risk"], 1):
        lines.append(
            f"\n{i}. [{r['risk_score']}/100] {r['title']}\n"
            f"   Reasons: {'; '.join(r['reasons'])}\n   Recommendation: {r['recommendation']}"
        )
    return "\n".join(lines)


async def _call_tool(memory, user_id: str, name: str, args: dict) -> str:
    if name == "get_context":
        return _tool_get_context(memory, user_id, args.get("query"), int(args.get("limit") or 5))
    if name == "store_context":
        return _tool_store_context(
            memory, user_id,
            args.get("decision"),
            args.get("context"),
            args.get("date"),
            args.get("source"),
            args.get("participants"),
            args.get("project") or "General"
        )
    if name == "search_decisions":
        return _tool_search_decisions(
            memory, user_id,
            args.get("topic"),
            args.get("date_from"),
            args.get("date_to"),
            args.get("person"),
            args.get("project")
        )
    if name == "find_similar_decisions":
        result = await di.find_similar_decisions(memory, user_id, args.get("query"), limit=int(args.get("limit") or 5))
        return _format_similar_decisions(result)
    if name == "detect_decision_patterns":
        result = await di.detect_decision_patterns(
            memory, user_id, scope=args.get("scope") or "all", lookback_days=int(args.get("lookback_days") or 365)
        )
        return _format_decision_patterns(result)
    if name == "predict_decision_risk":
        result = await di.predict_decision_risk(
            memory, user_id, decision_id=args.get("decision_id") or None, scope=args.get("scope") or "all"
        )
        return _format_decision_risk(result)
    raise ValueError(f"Unknown tool name: {name}")


# ── JSON-RPC dispatch ───────────────────────────────────────────────────────────

def _result(req_id, result):
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _error(req_id, code, message):
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


async def _handle_message(msg: dict, memory, user_id: str, request: Request = None) -> dict | None:
    """Process one JSON-RPC message. Returns a response dict, or None for notifications."""
    method = msg.get("method")
    req_id = msg.get("id")
    params = msg.get("params") or {}

    # Notifications (no id) — acknowledge with no response body.
    if req_id is None:
        return None

    if method == "initialize":
        if request:
            scheme = request.headers.get("x-forwarded-proto", request.url.scheme)
            host = request.headers.get("x-forwarded-host", request.url.netloc)
            icon_url = f"{scheme}://{host}/mcp/icon.svg"
        else:
            icon_url = f"{config.BACKEND_URL.rstrip('/')}/mcp/icon.svg"

        return _result(req_id, {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {
                "name": "KAIROS",
                "version": "1.0.0",
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
            text = await _call_tool(memory, user_id, name, args)
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

    # Resolve SSE session if active — only if THIS request's authenticated
    # user_id matches the session's recorded owner (see _owned_session_queue).
    session_id = request.query_params.get("session_id") or request.headers.get("Mcp-Session-Id")
    sse_queue = _owned_session_queue(session_id, user_id)

    # JSON-RPC supports single messages and batches (a JSON array).
    if isinstance(body, list):
        responses = []
        for m in body:
            resp = await _handle_message(m, memory, user_id, request)
            if resp is not None:
                if sse_queue is not None:
                    await sse_queue.put(resp)
                else:
                    responses.append(resp)
        if sse_queue is not None:
            return Response(status_code=202)  # Response routed via SSE
        if not responses:
            return Response(status_code=202)
        return _format_response(responses)

    if not isinstance(body, dict):
        return JSONResponse(_error(None, -32600, "Invalid Request: expected a JSON object or array"), status_code=400)

    extra_headers = {}
    if body.get("method") == "initialize":
        # Keep incoming or issue new session id
        extra_headers["Mcp-Session-Id"] = session_id or uuid.uuid4().hex

    resp = await _handle_message(body, memory, user_id, request)
    if resp is None:
        return Response(status_code=202)  # notification — no body

    if sse_queue is not None:
        # Route response message back to client via the active SSE stream queue
        await sse_queue.put(resp)
        return Response(status_code=202)

    # Fallback to returning direct JSON (stateless Streamable-HTTP)
    return _format_response(resp, extra_headers)


@mcp_rpc_router.post("/mcp")
async def mcp_bearer_http(request: Request):
    """MCP endpoint for OAuth-authenticated clients (Claude.ai web connectors).
    Reads user_id from 'Authorization: Bearer {access_token}' header."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return JSONResponse(
            {"jsonrpc": "2.0", "id": None, "error": {"code": -32001, "message": "Bearer token required."}},
            status_code=401,
            headers={"WWW-Authenticate": 'Bearer realm="KAIROS"'},
        )
    user_id = verify_mcp_token(auth_header.removeprefix("Bearer ").strip())
    if not user_id:
        return JSONResponse(
            {"jsonrpc": "2.0", "id": None, "error": {"code": -32001, "message": "Invalid or revoked KAIROS token."}},
            status_code=401,
        )
    memory = request.app.state.memory
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(_error(None, -32700, "Parse error"), status_code=400)

    # Resolve SSE session if active — only if THIS request's authenticated
    # user_id matches the session's recorded owner (see _owned_session_queue).
    session_id = request.query_params.get("session_id") or request.headers.get("Mcp-Session-Id")
    sse_queue = _owned_session_queue(session_id, user_id)

    if isinstance(body, list):
        responses = []
        for m in body:
            resp = await _handle_message(m, memory, user_id, request)
            if resp is not None:
                if sse_queue is not None:
                    await sse_queue.put(resp)
                else:
                    responses.append(resp)
        if sse_queue is not None:
            return Response(status_code=202)  # Response routed via SSE
        if not responses:
            return Response(status_code=202)
        return _format_response(responses)

    if not isinstance(body, dict):
        return JSONResponse(_error(None, -32600, "Invalid Request: expected a JSON object or array"), status_code=400)

    extra_headers = {}
    if body.get("method") == "initialize":
        # Keep incoming or issue new session id
        extra_headers["Mcp-Session-Id"] = session_id or uuid.uuid4().hex

    resp = await _handle_message(body, memory, user_id, request)
    if resp is None:
        return Response(status_code=202)

    if sse_queue is not None:
        # Route response message back to client via the active SSE stream queue
        await sse_queue.put(resp)
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
    _active_sessions[session_id] = (user_id, queue)

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
    # OAuth URL (for Claude.ai web/mobile connectors — required by claude.ai platform)
    oauth_url = f"{base_url}/mcp"
    # Token-in-URL (for Claude Desktop local config and direct clients)
    token_url = f"{base_url}/mcp/u/{token}"
    return {
        "url": oauth_url,
        "token_url": token_url,
        "token": token,
        "tools": [t["name"] for t in TOOLS],
        "claude_desktop_config": {"mcpServers": {"kairos": {"url": token_url}}},
        "cursor_config": {"mcpServers": {"kairos": {"url": token_url}}},
        "instructions": {
            "claude_web_mobile": f"Settings → Connectors → Add custom connector → paste: {oauth_url}",
            "chatgpt": f"Settings → Connectors (developer mode) → Add → paste: {oauth_url}",
            "claude_desktop": "Paste claude_desktop_config into claude_desktop_config.json.",
        },
    }


@mcp_connect_router.post("/revoke")
def mcp_revoke(request: Request, current_user: UserProfile = Depends(get_current_user)):
    """Invalidate every MCP token previously issued to this user (URL tokens
    AND OAuth access tokens — both are verified by the same epoch check) and
    immediately mint a fresh one. Use this if a connect URL or token may have
    leaked, or when disconnecting an MCP client you no longer trust."""
    new_epoch = revoke_mcp_tokens(current_user.uid)
    new_token = mint_mcp_token(current_user.uid)
    scheme = request.headers.get("x-forwarded-proto", request.url.scheme)
    host = request.headers.get("x-forwarded-host", request.url.netloc)
    base_url = f"{scheme}://{host}"
    return {
        "revoked": True,
        "epoch": new_epoch,
        "token": new_token,
        "token_url": f"{base_url}/mcp/u/{new_token}",
    }
