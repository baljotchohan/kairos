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
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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


async def _ingestion_loop():
    """Run ingestion every INGEST_INTERVAL_MINUTES minutes."""
    interval = config.INGEST_INTERVAL_MINUTES * 60
    # Small initial delay so app is ready before first run
    await asyncio.sleep(10)

    while True:
        try:
            print(f"[Ingestion] Starting scheduled run...")
            await orchestrator.run_ingestion()
        except Exception as e:
            print(f"[Ingestion] Error: {e}")
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

# Also allow all *.vercel.app and *.hf.space origins via regex
_ALLOWED_ORIGIN_REGEX = r"https://(.*\.vercel\.app|.*\.hf\.space)"

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_origin_regex=_ALLOWED_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routes
from api.routes import router
from api.websocket import ws_router

app.include_router(router)
app.include_router(ws_router)


@app.get("/")
async def root():
    return {
        "name": "KAIROS",
        "tagline": "Every company forgets why. KAIROS never does.",
        "status": "running",
        "memory_stats": memory.graph.stats() if memory else {},
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
