# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

KAIROS is a **Company Organizational Memory OS** — 5 parallel AI agents ingest a company's Slack, email, Drive, Jira, and Zoom data, extract every decision and its context, and store it in a vector + relational + graph memory layer. Employees query it in natural language and get full decision history with sources in seconds.

**Hackathon:** AMD Developer Hackathon ACT II — deadline July 11, 2026. $10K+ prize.
**Demo company name for all fake data:** Helios Tech.

## Commands

```bash
# Backend
pip install -r requirements.txt
uvicorn api.main:app --reload --port 8000

# Frontend (once built)
cd frontend && npm install && npm run dev

# Full stack
docker-compose up --build

# MCP server standalone
python mcp_server.py

# Seed demo data and export Obsidian vault
python demo_graph.py
```

## Architecture — 4 Layers

```
Connectors → Agents → Core (Memory + Graph) → API + MCP + Frontend
```

**Connectors** (`connectors/`) — raw data fetch from Slack, Gmail, Drive, Jira, Zoom. No AI here, just API calls returning raw objects.

**Agents** (`agents/`) — wrap connectors, call Fireworks AI to classify messages as decisions and extract structured `Decision` objects. Five agents run in parallel via LangGraph: `slack_agent`, `email_agent`, `drive_agent`, `meeting_agent`, `synthesis_agent` (the orchestrator for queries).

**Core** (`core/`):
- `fireworks.py` — async httpx Fireworks AI client. All LLM and embedding calls go here. Never call OpenAI/Anthropic directly — AMD requirement.
- `memory.py` — `KairosMemory`: ChromaDB (semantic/vector) + SQLite (structured) + graph. Every `store()` call writes all three AND auto-syncs the Obsidian vault.
- `graph.py` — `DecisionGraph`: NetworkX + SQLite. Auto-links decisions by shared topics/participants. `add_decision(node, vault_path=...)` updates only changed Obsidian notes.
- `orchestrator.py` — LangGraph graph that fans out to 5 agents in parallel.

**API** (`api/`):
- `main.py` — FastAPI app, mounts routes + WebSocket `/ws`
- `routes/query.py` — `POST /api/v1/query`
- `routes/ingest.py` — `POST /api/v1/ingest`
- `routes/admin.py` — admin OAuth setup
- `routes/health.py` — `GET /health`
- `websocket.py` — streams ingestion progress + query tokens to frontend

**MCP Server** (`mcp_server.py`) — 3 tools over Streamable HTTP at `/mcp`:
- `get_context(query)` — semantic search, call before answering any company question
- `store_context(decision, context, participants, date, source, project)` — save to memory
- `search_decisions(topic, date_from, date_to, person, project)` — structured search

## Key Design Decisions

**All AI via Fireworks AI only** — model: `accounts/fireworks/models/qwen2p5-72b-instruct`, embeddings: `nomic-ai/nomic-embed-text-v1.5`, speech: `whisper-v3`. Base URL: `https://api.fireworks.ai/inference/v1`. OpenAI-compatible client pointed at Fireworks.

**Always stream** — FastAPI uses `StreamingResponse`, WebSocket sends tokens as they arrive. Never wait for full response.

**Always show sources** — every `Decision` stores `source_url`. Synthesis agent formats responses with source citations (Slack link, email thread, doc link).

**Dual memory** — ChromaDB for "find decisions about AWS" (semantic); SQLite for "decisions by John in Q3 2021" (exact/range). Both written on every `store()`.

**Obsidian auto-sync** — `memory.store()` → `graph.add_decision(vault_path=...)` → writes only the changed `.md` notes. `memory.rebuild_obsidian()` for full re-export.

**Permission scoping** — enforced at SQLite layer: admin sees all, manager sees team, employee sees own projects.

## SQLite Schema

```sql
decisions (id, text, context, participants, date, source_type, source_url, project, outcome, created_at)
sources   (id, decision_id, type, url, snippet)
people    (id, name, email, role, decisions_made)
projects  (id, name)
tags      (id, decision_id, tag_name)
-- graph tables (owned by graph.py):
relations (from_id, to_id, relation_type)
```

## Environment Variables

All defined in `config.py`. Copy `.env.example` → `.env`. Key vars:
- `FIREWORKS_API_KEY` — required for all AI
- `CHROMA_PERSIST_DIR` / `SQLITE_PATH` / `OBSIDIAN_VAULT` — memory paths
- `SLACK_BOT_TOKEN` / `SLACK_APP_TOKEN`
- `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` / `GOOGLE_REFRESH_TOKEN`
- `ZOOM_ACCOUNT_ID` / `ZOOM_CLIENT_ID` / `ZOOM_CLIENT_SECRET`
- `JIRA_URL` / `JIRA_EMAIL` / `JIRA_API_TOKEN`
- `FRONTEND_URL` (default `http://localhost:3000`)

## Build Order (Phase by Phase)

```
Phase 1 — Foundation        core/fireworks.py, core/memory.py, api/main.py, /health
Phase 2 — Core Intelligence synthesis_agent, mcp_server.py, WebSocket streaming
Phase 3 — Ingestion         slack_connector + slack_agent, demo data (Helios Tech)
Phase 4 — More connectors   gmail, drive agents
Phase 5 — Frontend          Next.js chat + SourcePanel + AdminSetup, dark theme
Phase 6 — Polish            Docker, demo video, README
Phase 7 — Submit            lablab.ai, public repo
```

## Non-Negotiables

- Never use OpenAI API key directly — always Fireworks base_url
- Every answer cites sources (Slack link / email / doc)
- Responses stream, never batch
- Dark theme UI throughout
- Docker must work before moving phases
- Demo data company name: **Helios Tech**
