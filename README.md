<div align="center">

# KAIROS

### The Company Organizational Memory OS

**"Every company forgets why it made its decisions. KAIROS never does."**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://www.python.org/)
[![Next.js 15](https://img.shields.io/badge/Next.js-15-black.svg)](https://nextjs.org/)
[![Docker](https://img.shields.io/badge/Docker-containerized-2496ED.svg)](https://www.docker.com/)
[![Fireworks AI](https://img.shields.io/badge/AI-Fireworks%20AI%20(AMD)-orange.svg)](https://fireworks.ai)
[![MCP](https://img.shields.io/badge/MCP-enabled-6E56CF.svg)](./docs/REMOTE_MCP.md)

**[Live App](https://kairos-coral-nine.vercel.app)** · **[API](https://baljot07-kairos-backend.hf.space/health)** · **[Remote MCP](./docs/REMOTE_MCP.md)** · Built for the **AMD Developer Hackathon ACT II**

</div>

---

## The Problem

```
New engineer joins the company.
"Why do we use AWS instead of GCP?"
Nobody knows. The person who decided left two years ago.
Takes six months of tribal-knowledge archaeology to piece together.

CEO asks: "Why are we paying this vendor $2.3M a year?"
Nobody knows. The contract was signed in 2019, auto-renewed
three times, and the person who signed it left in 2022.

Someone proposes a mobile app.
Nobody remembers the team tried this in 2021 and it failed —
so they're about to spend ₹40 lakhs finding out again.
```

Every company generates thousands of decisions a year — in Slack threads, email chains, Drive docs, Zoom calls, Notion pages. The reasoning behind them evaporates the moment the people who made them stop repeating the story out loud. Confluence, Notion, and SharePoint store the documents you *write*. Nobody stores the decisions you *make*.

## The Answer

KAIROS connects to the places decisions actually happen, reads everything, and asks one question of every message, thread, doc, and transcript: **was a decision made here?** If yes, it extracts what was decided, who was involved, what alternatives were considered, and why — and stores it permanently, with the source attached.

Ask it anything, in plain English:

> **"Why are we paying this vendor $2.3M a year?"**
> *Decision made in a Slack thread, Nov 2019. Contract signed by [name], who left in 2022. Auto-renewed 3 times since with no review. Original terms: $1.1M/year. → [Slack] [Email thread] [Contract doc]*

Four seconds. Fully sourced. No tribal knowledge required.

---

## What Makes This Different

| | Document stores (Confluence, Notion, SharePoint) | **KAIROS** |
|---|---|---|
| What it captures | What you deliberately write down | What actually got decided, wherever it happened |
| Where it looks | One app | Slack, Gmail, Drive, Notion, Zoom, Jira |
| Data model | Pages and folders | A **decision graph** — nodes are decisions, people, and sources; edges are shared topics, causality, and follow-ups |
| Retrieval | Keyword search | Semantic + structured + graph-neighbor hybrid search, routed by intent |
| Freshness | Only what got written up | On-demand **live** queries against your actual connected accounts, not just stored memory |
| AI integration | None, or bolted-on chat | A bidirectional MCP memory loop — any Claude/ChatGPT/Cursor session can pull context from and push new knowledge back into KAIROS |

---

## See It Work

### 1 — The Zombie Vendor
```
Q: "Why are we paying this vendor?"

KAIROS: You've been paying $191K/month for 3 years without
anyone knowing why. Signed Nov 2019 by John Smith (left 2022).
Auto-renewed 3 times, no review since. → [contract] [email thread]
```

### 2 — Instant Onboarding
```
Q: "Why do we use React instead of Vue?"

KAIROS: Frontend team voted 4-2 for React in a 2022 Slack thread.
Reasoning: larger hiring pool. Vue advocate was Priya (still on
the team — ask her for the counterargument). → [Slack thread]
```

### 3 — Don't Repeat the Mistake
```
Q: "Has anyone tried building a mobile app before?"

KAIROS: Yes — 2021 attempt, failed. No mobile expertise on the
team at the time. Cost: ₹40L. Killed at a March 2021 board
meeting. → [board notes] Want the full postmortem?
```

### 4 — Live, Not Just Remembered
```
Q: "How many unread emails do I have from finance?"

KAIROS doesn't search memory for this one — the Live Data Agent
queries Gmail directly, right now, and answers on the spot.
```

---

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌────────────────────────┐     ┌───────────────────────┐
│ CONNECTORS  │ ──▶ │    AGENTS    │ ──▶ │          CORE           │ ──▶ │  API · MCP · FRONTEND  │
│  raw fetch  │     │  ReAct loop  │     │  memory + graph + orch  │     │                        │
└─────────────┘     └──────────────┘     └────────────────────────┘     └───────────────────────┘

  Slack            base_agent.py            fireworks.py               FastAPI (main.py)
  Gmail            slack / email /           ├─ Fireworks (primary,     ├─ REST: decisions, query,
  Drive            drive / notion_agent      │  AMD hardware)           │  ingest, memory, admin
  Notion           meeting_agent (Zoom +     ├─ Groq (fallback)         ├─ WebSocket /ws — streamed
  Zoom             optional Whisper)         └─ Gemini (fallback)       │  chat + ingest progress
  Jira             synthesis_agent                                     ├─ OAuth per service
  (per-user OAuth, (extract + answer)        memory.py                 │  (encrypted at rest)
  encrypted at     intent_agent (routing)    ├─ ChromaDB (semantic)     │
  rest — Jira is   context_agent (hybrid     ├─ SQLite (structured,     └─ MCP — local stdio +
  the one global   retrieval)                │  one shared file)            remote OAuth/HTTP
  exception)       live_data_agent           └─ Obsidian auto-export        (get_context,
                   (on-demand live queries)                                  store_context,
                                              graph.py                       search_decisions)
                   All 9 agents share a      ├─ NetworkX decision graph
                   BaseAgent ReAct loop      ├─ Auto-linked by topic/       Next.js 15 frontend
                   with full execution       │  person, never cross-user   ├─ Hand-written canvas
                   tracing, fanned out       └─ Rendered live as an        │  force-directed physics
                   via LangGraph                interactive physics graph │  graph (no D3/WebGL)
                                                                           ├─ Streaming markdown +
                                              orchestrator.py              │  "Thinking" indicator
                                              ├─ Ingestion StateGraph      └─ Firebase Auth
                                              │  (per-user, every 12min)
                                              └─ Query pipeline: intent →
                                                 context → synthesis/live
```

**Every read and write is scoped to a `user_id`, and the search layer fails closed** — `semantic_search()`, `structured_search()`, and `hybrid_search()` return nothing at all if `user_id` is missing, rather than silently querying everyone's data. Each person connects their own Slack/Gmail/Drive/Notion/Zoom; nobody sees anyone else's.

---

## The Decision Graph

The most visible part of KAIROS is a **from-scratch Canvas 2D force-directed physics engine** — no D3, no WebGL, no graph library. Decisions, people, sources, dates, and outcomes are nodes; shared topics, causality, and follow-ups are spring-linked edges. Coulomb repulsion pushes nodes apart, springs pull related ones together, and the simulation cools to rest — then reheats the instant you drag a node, change a filter, or new data arrives. Retina-aware, themeable, fully interactive (drag, pan, zoom), with a live settings panel for tuning charge, link distance, and gravity.

## Bidirectional MCP Memory Loop

KAIROS exposes three tools over the Model Context Protocol — **on two transports**, so it works whether you're local or remote:

| Tool | What it does |
|---|---|
| `get_context(query)` | Semantic search — call before answering any question about the company or user's history |
| `store_context(decision, context, participants, date, source, project)` | Save newly learned information straight back into KAIROS |
| `search_decisions(topic, date_from, date_to, person)` | Structured, filtered search over the decision log |

- **Local** — `mcp_server.py`, stdio transport, drop into your Claude Desktop or Cursor config.
- **Remote** — full OAuth 2.0 + RFC 7591 dynamic client registration (`api/routes/mcp_oauth.py`, `mcp_remote.py`), so ChatGPT, Cursor, Antigravity, or any web-based MCP client can connect with a one-click per-user login — no config file needed. See [`docs/REMOTE_MCP.md`](./docs/REMOTE_MCP.md).

The result: KAIROS gives the model context before it answers, and the model pushes new knowledge back into KAIROS as it learns things — both sides get smarter over time.

---

## Tech Stack

<table>
<tr><td valign="top">

**Backend**
- Python 3.11+, FastAPI, Uvicorn
- WebSocket streaming throughout
- LangGraph (ingestion fan-out + query pipeline)
- ChromaDB (vector) + SQLite/WAL (structured) + NetworkX (graph)
- Firebase Admin SDK (auth)
- Fernet envelope encryption (OAuth tokens at rest)
- Whisper (optional meeting transcription)

</td><td valign="top">

**AI Models** *(auto-fallback chain)*
- **Fireworks AI** — `qwen3p7-plus` (primary, AMD hardware)
- **Groq** — `llama-v3p3-70b` / `llama-3.1-8b-instant` (fallback)
- **Gemini** — `gemini-2.0-flash` (fallback)
- Embeddings: Gemini → Fireworks `nomic-embed-text-v1.5` → local
- One OpenAI-compatible client interface — never calls OpenAI or Anthropic directly

</td></tr>
<tr><td valign="top">

**Frontend**
- Next.js 15 (App Router, Turbopack)
- React 19 + TypeScript
- Tailwind CSS, CSS-variable theming (dark by default)
- Firebase Auth (Google + anonymous)
- Hand-written canvas physics + markdown renderer — zero animation/chart dependencies

</td><td valign="top">

**Connectors & Infra**
- Slack (Web API + Socket Mode bot), Gmail, Drive, Notion, Zoom, Jira
- MCP: local stdio + remote OAuth/HTTP
- Docker + docker-compose (2 services, health-checked)
- Hosted: Hugging Face Space (backend) + Vercel (frontend)
- MIT Licensed

</td></tr>
</table>

---

## Quickstart

### Option A — Docker (recommended)

```bash
git clone https://github.com/baljotchohan/kairos.git
cd kairos
cp .env.example .env        # fill in at least FIREWORKS_API_KEY
docker-compose up --build
```

Backend → `http://localhost:8000` · Frontend → `http://localhost:3000`

### Option B — Run locally

```bash
# Backend
pip install -r requirements.txt
cp .env.example .env
uvicorn api.main:app --reload --port 8000

# Frontend (separate terminal)
cd frontend
npm install
npm run dev

# Optional: seed Helios Tech demo data + export the Obsidian vault
python demo_graph.py
```

### Connect your accounts

Sign in, then go to `/integrations` and connect Slack, Gmail/Drive, Notion, and/or Zoom — each is a one-click OAuth popup. Ingestion picks up new decisions automatically every 12 minutes, or trigger it on demand from the dashboard.

### Connect an MCP client

**Local (Claude Desktop / Cursor)** — add to your MCP config:
```json
{
  "mcpServers": {
    "kairos": { "command": "python", "args": ["/path/to/kairos/mcp_server.py"] }
  }
}
```

**Remote (any MCP client, no local install)** — see [`docs/REMOTE_MCP.md`](./docs/REMOTE_MCP.md) for the one-click OAuth connect URL.

---

## API Reference

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Health check |
| `POST` | `/query` | Ask a question synchronously |
| `WS` | `/ws` | Streamed chat, ingestion progress, and live stats |
| `GET` | `/decisions` | List the current user's decisions |
| `GET` | `/decisions/search` | Semantic / structured / hybrid search |
| `GET` | `/decisions/{id}` | Fetch a single decision |
| `POST` | `/store` | Manually store a decision |
| `GET` | `/graph/stats` | Decision graph node/edge counts |
| `POST` | `/graph/export/obsidian` | Force a full Obsidian vault re-export |
| `POST` | `/ingest` | Trigger background ingestion |
| `GET` | `/ingest/status/{task_id}` | Poll ingestion progress |
| `GET` | `/sessions`, `/profile` | Conversation history + learned user profile |
| `GET` | `/oauth/{service}/start` | Begin OAuth for `slack` / `gmail` / `drive` / `notion` / `zoom` / `jira` |
| `GET` | `/oauth/status` | Per-user connection status for every service |
| `POST` | `/oauth/disconnect/{service}` | Revoke a connection |

Full request/response shapes live in `api/routes/`.

---

## Project Structure

```
kairos/
├── agents/          9 agents — base_agent (ReAct), slack/email/drive/notion/meeting,
│                    synthesis, intent, context, live_data
├── connectors/      slack (+ bot), gmail, drive, notion, zoom, jira
├── core/            fireworks (LLM chain), memory (Chroma+SQLite), graph (NetworkX+Obsidian),
│                    orchestrator (LangGraph), user_memory, live_connectors, mcp_auth, token_crypto
├── api/
│   ├── main.py      FastAPI app, lifespan, per-user ingestion loop, CORS, rate limiting
│   ├── auth.py      Firebase verification + demo-user routing
│   ├── websocket.py streamed query / ingest / stats
│   └── routes/      health, query, ingest, decisions, memory, admin, oauth, mcp_oauth, mcp_remote
├── mcp_server.py    local stdio MCP server
├── frontend/        Next.js 15 app — dashboard, integrations, landing page, decision graph
├── data/demo/       Helios Tech demo dataset
├── docs/            REMOTE_MCP.md — remote MCP OAuth model
├── tests/           test_memory.py, test_api.py
├── scripts/         deploy_hf.sh, seed_demo_data.py, Google auth helpers
├── Dockerfile, Dockerfile.hf, frontend/Dockerfile, docker-compose.yml
├── requirements.txt, .env.example
└── CLAUDE.md        full technical architecture reference
```

---

## Environment Variables

See [`.env.example`](./.env.example) for the complete list. At minimum you need:

```bash
FIREWORKS_API_KEY=      # required — primary model provider (AMD hardware)
GROQ_API_KEY=           # optional — fallback if Fireworks is rate-limited
GEMINI_API_KEY=         # optional — fallback + primary embeddings
TOKEN_ENCRYPTION_KEY=   # recommended in production — encrypts stored OAuth tokens
FIREBASE_SERVICE_ACCOUNT=  # required for real auth (JSON, or use GOOGLE_APPLICATION_CREDENTIALS)
```

Connector credentials (`SLACK_*`, `GOOGLE_*`, `NOTION_*`, `ZOOM_*`, `JIRA_*`) are optional individually — connect only the services you want.

---

## Built For

**AMD Developer Hackathon ACT II** (lablab.ai × AMD) — Track 3: Unicorn 🦄. All model inference routes primarily through **Fireworks AI** on AMD hardware, with Groq and Gemini as automatic fallback providers for resilience. Fully Docker-containerized, MIT licensed.

## License

[MIT](./LICENSE) © 2026 Baljot Singh Chohan

---

<div align="center">

*KAIROS — built by [Baljot](https://github.com/baljotchohan) / Antigravity*

</div>
