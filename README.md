<div align="center">

# KAIROS

### The Company Organizational Memory OS

**"Every company forgets why it made its decisions. KAIROS never does."**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://www.python.org/)
[![Next.js 15](https://img.shields.io/badge/Next.js-15-black.svg)](https://nextjs.org/)
[![Docker](https://img.shields.io/badge/Docker-containerized-2496ED.svg)](https://www.docker.com/)
[![Fireworks AI](https://img.shields.io/badge/AI-Fireworks%20AI%20(AMD)-orange.svg)](https://fireworks.ai)
[![MCP](https://img.shields.io/badge/MCP-6%20tools-6E56CF.svg)](./docs/REMOTE_MCP.md)

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

Every company generates thousands of decisions a year — in Slack threads, email chains, Drive docs, Zoom calls, Notion pages, PRs. The reasoning behind them evaporates the moment the people who made them stop repeating the story out loud. Confluence, Notion, and SharePoint store the documents you *write*. Nobody stores the decisions you *make* — and nobody watches those decisions for the ones quietly rotting.

## The Answer

KAIROS connects to the places decisions actually happen, reads everything, and asks one question of every message, thread, doc, and transcript: **was a decision made here?** If yes, it extracts what was decided, who was involved, what alternatives were considered, and why — stores it permanently with the source attached, and then keeps watching it: flagging contradictions, stale vendor spend, single-point-of-failure decision makers, and decisions overdue for review.

Ask it anything, in plain English:

> **"Why are we paying this vendor $2.3M a year?"**
> *Decision made in a Slack thread, Nov 2019. Contract signed by [name], who left in 2022. Auto-renewed 3 times since with no review. Original terms: $1.1M/year. → [Slack] [Email thread] [Contract doc]*

Four seconds. Fully sourced. No tribal knowledge required.

---

## What Makes This Different

| | Document stores (Confluence, Notion, SharePoint) | **KAIROS** |
|---|---|---|
| What it captures | What you deliberately write down | What actually got decided, wherever it happened |
| Where it looks | One app | Slack, Gmail, Drive, Notion, Zoom, Jira, GitHub |
| Data model | Pages and folders | A **decision graph** — nodes are decisions, people, and sources; edges are shared topics, causality, and follow-ups |
| Retrieval | Keyword search | Semantic + structured + graph-neighbor hybrid search, routed by intent |
| Freshness | Only what got written up | On-demand **live** queries against your actual connected accounts, not just stored memory |
| Proactivity | Passive — waits to be searched | **Decision Intelligence** — surfaces contradictions, stale vendor spend, bus-factor risk, and a rolling Decision Debt Score without being asked |
| AI integration | None, or bolted-on chat | A bidirectional MCP memory loop, 6 tools deep — any Claude/ChatGPT/Cursor session can pull context from and push new knowledge back into KAIROS |

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

### 5 — Caught Before It Was Asked
```
Nobody asked anything. Decision Intelligence flagged it anyway:

⚠ bus_factor_risk (high) — 4 of the last 6 infra decisions were
made solely by one departed engineer, none with a documented
follow-up. Debt Score: 62/100. → Review these before the next
infra hire needs to make the same calls blind.
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
  Drive            drive / notion /          │  AMD hardware)           │  ingest, memory, admin,
  Notion           github_agent              ├─ Groq (fallback)         │  agents (personas)
  Zoom             meeting_agent (Zoom +     └─ Gemini (fallback)       ├─ WebSocket /ws — streamed
  Jira             optional Whisper)                                   │  chat + ingest progress
  GitHub           synthesis_agent           memory.py                 ├─ OAuth per service
  (per-user OAuth, (extract + answer)        ├─ ChromaDB (semantic)     │  (encrypted at rest)
  encrypted at     intent_agent (routing)    ├─ SQLite (structured,     │
  rest — Jira is   context_agent (hybrid     │  one shared file)        └─ MCP — local stdio +
  the one global   retrieval)                └─ Obsidian auto-export        remote OAuth/HTTP
  exception)       live_data_agent                                          6 tools: get_context,
                   (on-demand live queries)  graph.py                       store_context,
                   research_agent            ├─ NetworkX decision graph     search_decisions,
                   (multi-step deep dives)   ├─ Auto-linked by topic/       find_similar_decisions,
                                              │  person, never cross-user   detect_decision_patterns,
                   All 11 agents share a     └─ Rendered live as an        predict_decision_risk
                   BaseAgent ReAct loop         interactive physics graph
                   with full execution                                    Next.js 15 frontend
                   tracing, fanned out       decision_intelligence.py     ├─ Hand-written canvas
                   via LangGraph             ├─ find_similar_decisions    │  force-directed physics
                                              │  (precedent vs. noise)     │  graph (no D3/WebGL)
                   personas.py                ├─ detect_decision_patterns ├─ Streaming markdown +
                   per-user agent display     │  (contradictions, stale   │  "Thinking" indicator
                   name + tone, presentation  │  vendors, bus-factor)     ├─ Settings → Agents
                   layer only                 ├─ predict_decision_risk    │  (rename/tune personas)
                                              └─ compute_debt_score        └─ Firebase Auth
                                                 (pure SQL/graph, no LLM)
                                              orchestrator.py
                                              ├─ Ingestion StateGraph
                                              │  (per-user, every 12min)
                                              └─ Query pipeline: intent →
                                                 context → synthesis/live
```

**Every read and write is scoped to a `user_id`, and the search layer fails closed** — `semantic_search()`, `structured_search()`, `hybrid_search()`, and every function in `decision_intelligence.py` return nothing at all if `user_id` is missing, rather than silently querying everyone's data. Each person connects their own Slack/Gmail/Drive/Notion/Zoom/GitHub; nobody sees anyone else's.

---

## The Decision Graph

The most visible part of KAIROS is a **from-scratch Canvas 2D force-directed physics engine** — no D3, no WebGL, no graph library. Decisions, people, sources, dates, and outcomes are nodes; shared topics, causality, and follow-ups are spring-linked edges. Coulomb repulsion pushes nodes apart, springs pull related ones together, and the simulation cools to rest — then reheats the instant you drag a node, change a filter, or new data arrives. Retina-aware, themeable, fully interactive (drag, pan, zoom), with a live settings panel for tuning charge, link distance, and gravity.

## Decision Intelligence

Underneath the graph, KAIROS doesn't just wait to be asked — it watches the decision log for organizational risk, all scoped per-user and fail-closed like everything else in `core/`:

| Capability | What it does |
|---|---|
| **Find similar decisions** | Semantic search over past decisions, then an LLM pass that separates genuine precedent from topically-similar noise |
| **Detect decision patterns** | Structurally flags `contradictory_outcome` clusters (same topic, conflicting outcomes), `unreviewed_vendor_spend` (stale vendor/contract decisions with no follow-up in 12+ months), and `bus_factor_risk` (3+ decisions made solely by one person) — severity is scored deterministically, the LLM only writes the prose |
| **Predict decision risk** | Scores individual decisions on staleness, financial/security/compliance impact, and ownership gaps; batches one LLM call to write a recommendation for the top offenders |
| **Decision Debt Score** | A pure SQL/graph rollup (`compute_debt_score` — no LLM call) shown as a live gauge on the dashboard: high-risk decisions out of total, with top offenders named |

Every one of these is also a first-class MCP tool (below), so any connected AI client can ask "have we seen this before?" or "what's rotting right now?" without a human opening the dashboard.

## Bidirectional MCP Memory Loop

KAIROS exposes **six tools** over the Model Context Protocol — **on two transports**, so it works whether you're local or remote:

| Tool | What it does |
|---|---|
| `get_context(query)` | Semantic search — call before answering any question about the company or user's history |
| `store_context(decision, context, participants, date, source, project)` | Save newly learned information straight back into KAIROS |
| `search_decisions(topic, date_from, date_to, person)` | Structured, filtered search over the decision log |
| `find_similar_decisions(query, limit)` | Precedent check — has anything like this been decided before, and what happened? |
| `detect_decision_patterns(scope, lookback_days)` | Scan for contradictions, unreviewed vendor spend, and bus-factor risk |
| `predict_decision_risk(decision_id, scope)` | Risk-score one decision or the whole log, with a concrete recommendation |

- **Local** — `mcp_server.py`, stdio transport, drop into your Claude Desktop or Cursor config.
- **Remote** — full OAuth 2.0 + RFC 7591 dynamic client registration (`api/routes/mcp_oauth.py`, `mcp_remote.py`), so ChatGPT, Cursor, Antigravity, or any web-based MCP client can connect with a one-click per-user login — no config file needed. See [`docs/REMOTE_MCP.md`](./docs/REMOTE_MCP.md).

The result: KAIROS gives the model context (and now, risk analysis) before it answers, and the model pushes new knowledge back into KAIROS as it learns things — both sides get smarter over time.

## Agent Personas

Every internal agent (`slack_agent`, `synthesis_agent`, `live_data_agent`, etc.) has a per-user display name and tone preset (professional / concise / analyst / custom), managed from **Settings → Agents** (`/settings/agents`) or the `/agents` REST API (`core/personas.py`, `api/routes/agents.py`). It's a presentation layer only — renaming "Slack Extraction Agent" to something else never touches its extraction or classification logic, and display names are sanitized before they can reach an LLM system prompt.

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
- Slack (Web API + Socket Mode bot), Gmail, Drive, Notion, Zoom, Jira, GitHub
- MCP: local stdio + remote OAuth/HTTP, 6 tools
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

Sign in, then go to `/integrations` and connect Slack, Gmail/Drive, Notion, GitHub, and/or Zoom — each is a one-click OAuth popup. Ingestion picks up new decisions automatically every 12 minutes, or trigger it on demand from the dashboard.

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
| `GET` | `/decisions/debt-score` | Decision Debt Score — high-risk count, total, top offenders |
| `GET` | `/decisions/{id}` | Fetch a single decision |
| `POST` | `/store` | Manually store a decision |
| `GET` | `/graph/stats` | Decision graph node/edge counts |
| `POST` | `/graph/export/obsidian` | Force a full Obsidian vault re-export |
| `POST` | `/ingest` | Trigger background ingestion |
| `GET` | `/ingest/status/{task_id}` | Poll ingestion progress |
| `GET` | `/sessions`, `/profile` | Conversation history + learned user profile |
| `GET` | `/agents` | List every agent with this user's persona override, or the default |
| `PUT` | `/agents/{agent_key}` | Rename an agent / change its tone (this user only) |
| `DELETE` | `/agents/{agent_key}` | Reset an agent back to its default persona |
| `GET` | `/oauth/{service}/start` | Begin OAuth for `slack` / `gmail` / `drive` / `notion` / `zoom` / `jira` / `github` |
| `GET` | `/oauth/status` | Per-user connection status for every service |
| `POST` | `/oauth/disconnect/{service}` | Revoke a connection |

Full request/response shapes live in `api/routes/`.

---

## Project Structure

```
kairos/
├── agents/          base_agent (ReAct) + 11 agents: slack/email/drive/notion/github/meeting,
│                    synthesis, intent, context, live_data, research
├── connectors/      slack (+ bot), gmail, drive, notion, zoom, jira, github
├── core/            fireworks (LLM chain), memory (Chroma+SQLite), graph (NetworkX+Obsidian),
│                    decision_intelligence (patterns/risk/debt score), personas (agent
│                    display names/tone), orchestrator (LangGraph), user_memory,
│                    live_connectors, mcp_auth, token_crypto
├── api/
│   ├── main.py      FastAPI app, lifespan, per-user ingestion loop, CORS, rate limiting
│   ├── auth.py      Firebase verification + demo-user routing
│   ├── websocket.py streamed query / ingest / stats
│   └── routes/      health, query, ingest, decisions, memory, admin, agents (personas),
│                     oauth, mcp_oauth, mcp_remote
├── mcp_server.py    local stdio MCP server — 6 tools (memory + decision intelligence)
├── frontend/        Next.js 15 app — dashboard (chat/metrics/decisions/connectors/agents/mcp),
│                    integrations, settings/agents (persona editor), landing page
├── data/demo/       Helios Tech demo dataset
├── docs/            REMOTE_MCP.md — remote MCP OAuth model
├── tests/           unit + integration coverage: memory, api, decision_intelligence, personas,
│                    mcp_auth, mcp_oauth, multi-tenant isolation, synthesis_agent, websocket
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

Connector credentials (`SLACK_*`, `GOOGLE_*`, `NOTION_*`, `ZOOM_*`, `JIRA_*`, `GITHUB_*`) are optional individually — connect only the services you want.

---

## Built For

**AMD Developer Hackathon ACT II** (lablab.ai × AMD) — Track 3: Unicorn 🦄. All model inference routes primarily through **Fireworks AI** on AMD hardware, with Groq and Gemini as automatic fallback providers for resilience. Fully Docker-containerized, MIT licensed.

## License

[MIT](./LICENSE) © 2026 Baljot Singh Chohan

---

<div align="center">

*KAIROS — built by [Baljot](https://github.com/baljotchohan) / Antigravity*

</div>
