"""
KAIROS FastAPI Application — main entry point.

Startup:
  1. Init memory (ChromaDB + SQLite + graph)
  2. Build orchestrator
  3. Mount routes + WebSocket
  4. Schedule background ingestion loop
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

log = logging.getLogger(__name__)

from config import config
from core.memory import KairosMemory
from core.orchestrator import KairosOrchestrator
from connectors.slack_bot import SlackBot


# ── Globals (single instances shared across the app) ─────────────────────────

memory: KairosMemory = None
orchestrator: KairosOrchestrator = None
slack_bot: SlackBot = None


# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    global memory, orchestrator, slack_bot

    print("🧠 KAIROS starting up...")

    # Init memory
    memory = KairosMemory()
    app.state.memory = memory

    # Init orchestrator
    orchestrator = KairosOrchestrator(memory=memory)
    app.state.orchestrator = orchestrator

    # Optional demo seed — OFF by default. KAIROS runs on REAL ingested data
    # from the user's connected accounts (Slack/Gmail/Drive/Jira/Zoom). Set
    # SEED_DEMO_DATA=true only if you want the Helios Tech sample decisions.
    if config.SEED_DEMO_DATA:
        try:
            # Seed Helios Tech sample decisions under a dedicated demo account
            # (config.DEMO_USER_ID) so they show ONLY for the demo login and never
            # leak into real users' scoped views. Idempotent on the demo account;
            # because the Helios nodes use fixed IDs, this also migrates any legacy
            # user_id="" Helios rows from earlier seeds onto the demo scope.
            demo_uid = config.DEMO_USER_ID
            if memory.graph.stats(user_id=demo_uid).get("total_decisions", 0) == 0:
                from data.demo.helios_tech import get_demo_decisions
                decisions = get_demo_decisions()
                print(f"🌱 SEED_DEMO_DATA=true — seeding {len(decisions)} demo decisions under '{demo_uid}'...")
                for node in decisions:
                    memory.store(node, user_id=demo_uid)
                print(f"✅ Seeded demo account '{demo_uid}' — {memory.graph.stats(user_id=demo_uid)}")
        except Exception as e:
            print(f"⚠️  Demo seed skipped: {e}")

    print(f"✅ Memory ready — {memory.graph.stats()}")

    # Start Slack bot (listens for @KAIROS mentions via Socket Mode)
    slack_bot = SlackBot(orchestrator=orchestrator)
    app.state.slack_bot = slack_bot
    asyncio.create_task(slack_bot.start())

    # Start background ingestion loop
    task = asyncio.create_task(_ingestion_loop())
    app.state.ingestion_task = task

    yield  # app is running

    # Shutdown
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    await slack_bot.stop()
    print("👋 KAIROS shut down cleanly")


def _get_active_user_ids() -> list[str]:
    """Return all user UIDs that have at least one OAuth token stored."""
    import sqlite3 as _sqlite3
    try:
        with _sqlite3.connect(config.SQLITE_PATH) as conn:
            rows = conn.execute(
                "SELECT DISTINCT user_uid FROM oauth_tokens WHERE user_uid IS NOT NULL AND user_uid != ''"
            ).fetchall()
            return [r[0] for r in rows]
    except Exception:
        return []


async def _ingestion_loop():
    """Run ingestion every INGEST_INTERVAL_MINUTES minutes, concurrently per connected user."""
    interval = config.INGEST_INTERVAL_MINUTES * 60
    # Small initial delay so app is ready before first run
    await asyncio.sleep(10)

    while True:
        user_ids = await asyncio.to_thread(_get_active_user_ids)
        if not user_ids:
            print("[Ingestion] No connected users — skipping run.")
        else:
            async def run_for_user(uid: str):
                try:
                    from core.user_memory import UserMemory
                    um = UserMemory()
                    profile = um.get_profile(uid)
                    auto_ext = profile.metadata.get("auto_extraction", True)
                    if not auto_ext:
                        print(f"[Ingestion] Background ingestion is disabled for user {uid} (auto_extraction=False). Skipping.")
                        return

                    print(f"[Ingestion] Starting run for user {uid}...")
                    await orchestrator.run_ingestion(user_id=uid)
                except Exception as e:
                    print(f"[Ingestion] Error for user {uid}: {e}")

            # Execute user ingestions concurrently
            await asyncio.gather(*(run_for_user(uid) for uid in user_ids))
        await asyncio.sleep(interval)


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="KAIROS",
    description="Company Organizational Memory OS — AMD Developer Hackathon ACT II",
    version="1.0.0",
    lifespan=lifespan,
)

_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3001",
    config.FRONTEND_URL,
    # Vercel deployments (all previews + production)
    "https://kairos-memory-os.vercel.app",
]

# Allow this project's Vercel previews + HF Space origins. Anchored to the
# actual project slug ("kairos-memory-os-...") rather than a bare "kairos"
# substring anywhere in the hostname — Vercel/HF Spaces are shared hosting
# where anyone can self-register a project containing that substring (e.g.
# "kairos-phish.vercel.app" or "x-kairos-y.hf.space" both matched the old
# regex). This narrows the bar to registering a project with our EXACT slug,
# not merely containing our name.
_ALLOWED_ORIGIN_REGEX = r"https://kairos-memory-os(-[a-z0-9-]+)?\.(vercel\.app|hf\.space)"

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_origin_regex=_ALLOWED_ORIGIN_REGEX,
    # No cookie-based auth anywhere in this app (Firebase bearer tokens only;
    # MCP auth is a bearer/URL token — confirmed no `credentials: 'include'`
    # fetch anywhere in frontend/, no Set-Cookie anywhere in api/). Credentialed
    # CORS is what lets a malicious origin ride a victim's session — since
    # there's no session to ride, there's no reason to opt into that risk
    # category at all, regardless of how precise the origin regex is.
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class _MCPCORSMiddleware:
    """Pure-ASGI middleware: allow any origin on /mcp/* paths.
    The MCP endpoints use token-in-URL auth (no cookies), so open CORS is safe.
    This runs BEFORE CORSMiddleware (added after it → wraps around it) so OPTIONS
    preflights from claude.ai / chatgpt.com / cursor.com are handled correctly
    instead of being rejected by the stricter API-route CORS policy."""

    _CORS = [
        (b"access-control-allow-origin", b"*"),
        (b"access-control-allow-methods", b"GET, POST, OPTIONS, DELETE"),
        (b"access-control-allow-headers", b"content-type, accept, authorization, mcp-session-id, mcp-protocol-version"),
        (b"access-control-expose-headers", b"mcp-session-id"),
        (b"access-control-max-age", b"86400"),
    ]

    def __init__(self, app, **_kwargs):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not scope.get("path", "").startswith("/mcp/"):
            await self.app(scope, receive, send)
            return

        if scope.get("method") == "OPTIONS":
            await send({
                "type": "http.response.start",
                "status": 200,
                "headers": self._CORS + [(b"content-length", b"0")],
            })
            await send({"type": "http.response.body", "body": b"", "more_body": False})
            return

        # Strip the origin header so CORSMiddleware (inner) doesn't add its own
        # Access-Control-Allow-Origin and create a duplicate-header conflict.
        clean_headers = [
            (k, v) for k, v in scope.get("headers", []) if k.lower() != b"origin"
        ]
        scope = {**scope, "headers": clean_headers}

        async def inject_cors(event):
            if event["type"] == "http.response.start":
                event = {**event, "headers": list(event.get("headers", [])) + self._CORS}
            await send(event)

        await self.app(scope, receive, inject_cors)


# Must be added AFTER CORSMiddleware so it wraps around it (Starlette inserts at
# position 0, so the last-added middleware is the outermost = runs first).
app.add_middleware(_MCPCORSMiddleware)


# ── Lightweight in-memory rate limiting (per client IP) ────────────────────────
# Protects the expensive LLM/connector/MCP paths from abuse without adding a
# dependency. Fixed window; fine for a single-process deployment.
import time as _time
from collections import defaultdict, deque

_RL_WINDOW = 60.0   # seconds
_RL_MAX = 120       # max requests per window per IP across /api/* and /mcp/*
_rl_hits: dict[str, deque] = defaultdict(deque)
# _rl_hits never evicted an IP whose deque had fully expired — under sustained
# unique-IP traffic (scraper/bot churn, IPv6 rotation) this dict grows for the
# entire process lifetime. Sweep it at most once per window instead.
_rl_last_sweep = [0.0]


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    path = request.url.path
    if path.startswith("/api/") or path.startswith("/mcp/"):
        # This deployment always sits behind exactly one trusted reverse proxy
        # (HF Space / Vercel's rewrite proxy). That proxy appends the real
        # connecting IP as the RIGHTMOST entry of X-Forwarded-For — anything
        # to its left is client-supplied and trivially forgeable, so trusting
        # the leftmost entry let any caller fake a fresh IP on every request
        # and bypass the limiter entirely. Only the rightmost hop is trustworthy.
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            ip = forwarded.split(",")[-1].strip()
        else:
            ip = request.client.host if request.client else "unknown"
        now = _time.time()
        hits = _rl_hits[ip]
        while hits and now - hits[0] > _RL_WINDOW:
            hits.popleft()
        if len(hits) >= _RL_MAX:
            return JSONResponse(
                {"detail": "Rate limit exceeded. Please slow down and try again shortly."},
                status_code=429,
                headers={"Retry-After": "30"},
            )
        hits.append(now)

        if now - _rl_last_sweep[0] > _RL_WINDOW:
            _rl_last_sweep[0] = now
            stale_ips = [k for k, v in _rl_hits.items() if not v or now - v[-1] > _RL_WINDOW]
            for k in stale_ips:
                _rl_hits.pop(k, None)
    return await call_next(request)

# Mount routes
from api.routes import router
from api.websocket import ws_router
from api.routes.mcp_remote import mcp_rpc_router
from api.routes.mcp_oauth import mcp_oauth_public_router, mcp_oauth_api_router

app.include_router(router)
app.include_router(ws_router)
app.include_router(mcp_rpc_router)
# OAuth 2.0 server for Claude.ai connector auth (/.well-known/*, /oauth/*)
app.include_router(mcp_oauth_public_router)
# OAuth complete endpoint called by login page: POST /api/mcp/oauth/complete
app.include_router(mcp_oauth_api_router, prefix="/api")


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    log.error("Unhandled exception on %s %s", request.method, request.url.path, exc_info=exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected error occurred. Please try again."},
    )


@app.get("/")
async def root():
    return {
        "name": "KAIROS",
        "tagline": "Every company forgets why. KAIROS never does.",
        "status": "running",
        # NOTE: no global memory_stats here — that would leak cross-tenant
        # aggregate counts on a public, unauthenticated endpoint. Per-user
        # stats are served (scoped) via /admin/status and the WebSocket.
    }


@app.get("/health")
async def health():
    return {"status": "ok"}


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api.main:app",
        host=config.HOST,
        port=config.PORT,
        reload=config.DEBUG,
        log_level="info",
    )
