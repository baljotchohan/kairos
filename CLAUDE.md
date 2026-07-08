# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

KAIROS is a **Company Organizational Memory OS** — AI agents connect to a person's Slack, Gmail, Drive, Jira, Zoom, Notion, and GitHub, extract every decision and its context, and store it in a vector + relational + graph memory layer. Users query it in natural language over chat or WebSocket and get full decision history with sources in seconds. A hand-written canvas physics engine renders the decision graph as an interactive force-directed network.

**Hackathon:** AMD Developer Hackathon ACT II — deadline July 11, 2026. $10K+ prize.
**Demo company name for all fake data:** Helios Tech (gated behind `DEMO_USER_ID` / `DEMO_LOGIN_EMAIL` — real users never see it).

**Architecture model:** KAIROS is **per-user**, not company-wide-admin-installed. Each signed-in user connects their own Slack/Gmail/Drive/Notion/Zoom/Jira/GitHub via OAuth from `/integrations`, and every memory read/write is scoped to their `user_id`. Per-user Jira OAuth (full 3LO flow with Atlassian cloud_id resolution + refresh tokens, `api/routes/oauth.py`'s `jira_start`/`jira_callback` + `connectors/jira_connector.py`) is **fully implemented in code** — it's just not live in this deployment because `JIRA_CLIENT_ID`/`JIRA_CLIENT_SECRET` were never registered at developer.atlassian.com and set in `.env` (a one-time external credential-provisioning step, not a code gap; see `.env.example`). Until that's done, Jira falls back to a single global service-account credential, usable only by the user named in `JIRA_OWNER_UID`. Zoom has a narrower equivalent fallback: Server-to-Server auth against one global `ZOOM_CLIENT_ID`/`ZOOM_ACCOUNT_ID`, gated to `ZOOM_OWNER_UID` and explicitly disabled (`allow_s2s=False`) for every other user's connector.

## Commands

```bash
# Backend
pip install -r requirements.txt
uvicorn api.main:app --reload --port 8000

# Frontend
cd frontend && npm install && npm run dev   # Next.js 15 + Turbopack

# Full stack
docker-compose up --build

# MCP server standalone (stdio, for Claude Desktop / Cursor)
python mcp_server.py

# Seed demo data and export Obsidian vault
python demo_graph.py

# Tests
pytest
```

## Architecture — 4 Layers

```
Connectors → Agents → Core (Memory + Graph + Orchestration) → API + MCP + Frontend
```

**Connectors** (`connectors/`) — raw data fetch, no AI. Each wraps one external API:
- `slack_connector.py` — Slack Web API (channels, history, workspace info)
- `slack_bot.py` — Slack Socket Mode listener, routes @KAIROS mentions to the orchestrator
- `gmail_connector.py` — Gmail API (list/get/search messages)
- `drive_connector.py` — Google Drive API (list/search/export files)
- `jira_connector.py` — Jira REST API + JQL search (global credentials, see above)
- `zoom_connector.py` — Zoom API (recordings + transcription URLs)
- `notion_connector.py` — Notion API (page/database query, recursive block retrieval)
- `github_connector.py` — GitHub REST API (PRs with review comments, issues with discussion, across the user's most-active repos); also exposes live-query methods (list_repos, my_open_pull_requests, my_open_issues, search_issues) used by `live_data_agent.py`

**Agents** (`agents/`) — wrap connectors, call the LLM to classify content as decisions and extract structured `DecisionNode` objects. All inherit `base_agent.py`'s `BaseAgent`, which implements a ReAct loop (Reason → Act → Observe → Reflect) with a tool registry and execution tracing (`TraceStep`, `AgentResult`):
- `slack_agent.py`, `email_agent.py`, `drive_agent.py`, `notion_agent.py`, `github_agent.py` — fetch + extract decisions from their source
- `meeting_agent.py` — Zoom transcription; **gracefully degrades to `[]`** if `openai-whisper` isn't installed (it's excluded from the HF Docker image — ~2-3GB of PyTorch)
- `synthesis_agent.py` — the extraction brain: `extract_decisions()` turns raw content into `DecisionNode`s, `synthesize_answer()` answers user questions from retrieved memory with confidence scoring
- `intent_agent.py` — classifies each incoming query into `search` / `live_data` / `general_qa` / `ingest` and routes it
- `context_agent.py` — `resolve_context()` runs hybrid (semantic + keyword + source + graph-neighbor) retrieval plus user-profile lookup before synthesis
- `research_agent.py` — multi-step mode: decompose topic → search → refine → synthesize into a structured report
- `live_data_agent.py` — the largest agent (~900 lines): answers on-demand questions against a user's **live** connected accounts (e.g. "how many unread emails do I have", "what are my open PRs") rather than stored memory, via its own ReAct tool loop over Gmail/Drive/Slack/Jira/Zoom/Notion/GitHub, with an early-exit if the source isn't connected

**Core** (`core/`):
- `fireworks.py` — `FireworksClient`: async, multi-provider LLM client behind one interface. Text: **Fireworks (primary, AMD hardware) → Groq → Gemini**, auto-fallback on 429/dead key, provider probed before commit. Embeddings: **Gemini (primary) → Fireworks `nomic-embed-text-v1.5` (fallback) → ChromaDB local embeddings (last resort)**. Never calls OpenAI or Anthropic directly — always an OpenAI-compatible client pointed at one of the three base URLs above.
- `memory.py` — `KairosMemory`: composes ChromaDB (semantic/vector, metadata-filtered by `user_id`), a `DecisionGraph` (see below), and a `UserMemory`, all backed by one SQLite file. `store()` writes Chroma + SQLite + graph + Obsidian in one call.
- `graph.py` — `DecisionGraph`: NetworkX `DiGraph` + SQLite persistence, thread-safe via `RLock`. Auto-links new decisions to existing ones by shared topic/participant (`RelationType`: `same_topic`, `caused_by`, `same_person`, `same_timeframe`, `follow_up`) — **never across `user_id`**. Exports per-user Obsidian vaults (`KAIROS_{user_id}/`) with YAML frontmatter and `[[wikilinks]]`, updating only changed notes.
- `orchestrator.py` — `KairosOrchestrator`. Two jobs:
  1. **Ingestion** — a LangGraph `StateGraph` (`KairosState`) that fans out `gather_slack → gather_email → gather_drive → gather_meetings → gather_jira → gather_notion → synthesize`. `_synthesize()` round-robins sources, skips already-processed items (idempotent via the `inventory` table), caps extraction at `MAX_EXTRACT_PER_CYCLE` to stay under provider TPM limits.
  2. **Query** (`query_with_memory`) — session resume (30-min idle boundary) → `IntentAgent` → `ContextAgent` → `SynthesisAgent` or `LiveDataAgent` depending on intent → stream tokens to the WebSocket callback → return answer + sources + confidence + traces.
- `user_memory.py` — `UserMemory`: per-user `ConversationTurn` history (session-grouped) and a learned `UserProfile` (department, role context, frequent topics) that the LLM updates over time.
- `live_connectors.py` — reads a user's encrypted OAuth rows and builds live connector instances on demand (`build_connectors_for_user`); handles token refresh callbacks.
- `mcp_auth.py` — mints/verifies HMAC-signed per-user tokens used by the local and remote MCP endpoints.
- `token_crypto.py` — Fernet envelope encryption for `oauth_tokens.token_data` (`TOKEN_ENCRYPTION_KEY`); falls back to plaintext only when `DEBUG` and no key is set.

**API** (`api/`):
- `main.py` — FastAPI app. Lifespan startup builds `KairosMemory` + `KairosOrchestrator`, seeds demo data if `SEED_DEMO_DATA=true`, starts the Slack Socket Mode bot, and schedules a background `_ingestion_loop()` that runs `orchestrator.run_ingestion(user_id=uid)` concurrently for every UID with a row in `oauth_tokens`, every `INGEST_INTERVAL_MINUTES`. CORS allows localhost, Vercel previews, and HF Spaces; a separate `_MCPCORSMiddleware` allows any origin on `/mcp/*` (auth is a bearer/URL token, not cookies). Fixed-window rate limiting: 120 req/min/IP.
- `auth.py` — Firebase Admin SDK verifies ID tokens (`verify_id_token(..., check_revoked=True)`), detects anonymous sign-in, and maps a configured `DEMO_LOGIN_EMAIL` to `DEMO_USER_ID` so only that login sees Helios Tech data. In `DEBUG`/test mode, tokens prefixed `simulated-`/`sim-` bypass Firebase entirely for local dev.
- `websocket.py` — `WS /ws?token=`. Three message types: `query` (streams tokens → final `done` with answer/sources/intent/confidence/traces/session_id), `ingest` (streams progress → `ingest_done`), `stats` (decision/relation counts).
- `routes/health.py` — `GET /health`
- `routes/query.py` — `POST /query` (synchronous, non-streaming variant of the WS query flow)
- `routes/ingest.py` — `POST /ingest` (kick off background ingestion), `GET /ingest/status/{task_id}`
- `routes/decisions.py` — `GET /decisions`, `GET /decisions/search` (semantic/structured/hybrid), `GET /decisions/{id}`, `POST /store`, `GET /graph/stats`, `POST /graph/export/obsidian`
- `routes/memory.py` — `GET /sessions`, `GET /sessions/{id}`, `DELETE /sessions/{id}`, `GET /profile`, `POST /profile/reset`
- `routes/admin.py` — `GET /admin/status`
- `routes/oauth.py` — per-service OAuth 2.0 start/callback for `slack`, `gmail`, `drive`, `jira`, `notion`, `zoom`, plus `GET /status` and `POST /disconnect/{service}`. State tokens are HMAC-signed with a 10-min expiry. Tokens are stored per `(user_uid, service)` in `oauth_tokens`, encrypted via `token_crypto.py`. **No env-var fallback** — `/status` reflects only that user's stored rows.
- `routes/mcp_oauth.py` — OAuth 2.0 discovery (`/.well-known/oauth-authorization-server`) + RFC 7591 dynamic client registration + authorize/token endpoints, so remote MCP clients (ChatGPT, Cursor, Antigravity, etc.) can authenticate a specific KAIROS user without a Claude-Desktop-style local config file.
- `routes/mcp_remote.py` — JSON-RPC 2.0 over HTTP (`initialize`, `ping`, `tools/list`, `tools/call`) for the OAuth-authenticated remote MCP transport described above. See `docs/REMOTE_MCP.md`.

**MCP** — two transports exposing the same 8 tools:
1. `mcp_server.py` — local, `FastMCP` over stdio, for Claude Desktop / Cursor config files. Scoped to `MCP_TENANT_ID`.
2. `api/routes/mcp_remote.py` + `mcp_oauth.py` — remote, Streamable HTTP with full OAuth, for any web-based MCP client, scoped per-user via a signed token from `mcp_auth.py`.

Memory tools (identical signature on both transports):
- `get_context(query, limit=5)` — semantic search, call before answering any question about the company/user's history
- `store_context(decision, context, participants, date, source, project)` — save a new decision to memory
- `search_decisions(topic, date_from, date_to, person, limit)` — structured filter search
- `find_similar_decisions(query, limit=5)` — precedent check via `core/decision_intelligence.py`
- `detect_decision_patterns(scope="all", lookback_days=365)` — proactive risk scan (contradictions, unreviewed vendor spend, bus-factor risk)
- `predict_decision_risk(decision_id="", scope="all")` — per-decision 0-100 risk score + recommendation

Control tools — act on the app, not just memory:
- `ask_kairos(question)` — runs the full `orchestrator.query_with_memory()` pipeline (intent → context → synthesis/live-data) and returns a sourced answer, same as the chat UI, instead of raw records
- `trigger_ingestion()` — fires `orchestrator.run_ingestion(user_id)` as a background task instead of waiting for the automatic 12-minute cycle. Has real side effects (live connector calls + LLM spend), so both transports independently rate-limit it to once per 3 minutes per user (`INGESTION_COOLDOWN_SECONDS`), and skip if that user's `ingestion_locks` entry is already held

## Frontend (`frontend/`)

Next.js 15 (App Router, Turbopack) + React 19 + TypeScript + Tailwind CSS. No animation library, no charting library, no state-management library — physics, markdown parsing, and charts are all hand-written. Firebase Auth (Google popup + anonymous), with a "simulation mode" fallback (mock auth via localStorage) when Firebase env vars are absent.

**Routes:**
- `app/page.tsx` — marketing landing page (constellation canvas hero, problem/agents/connectors/MCP-loop sections)
- `app/dashboard/page.tsx` — the app itself: chat / metrics / decisions-graph / connectors / AI agents / MCP server / conversational-memory tabs, all in one client component
- `app/integrations/page.tsx` — OAuth connect grid for all 6 services
- `app/oauth/login/page.tsx` — OAuth popup completion handler
- `app/api/oauth/*`, `app/api/mcp/route.ts` — Next.js route handlers that proxy/support the remote MCP OAuth flow (discovery, register, authorize, token, complete)

**Key components** (`frontend/components/`):
- `DecisionGraph.tsx` — the centerpiece. A from-scratch Canvas 2D force-directed physics engine (Coulomb repulsion + spring links + center gravity, velocity + damping, alpha cooling). Runs a continuous `requestAnimationFrame` loop that's demand-driven — it only keeps stepping physics while `alpha > 0.005`, and reheats on drag/pan/zoom/resize/settings-change/new-data. Retina-aware canvas scaling. Ships its own floating settings panel (display + physics tuning, persisted to `localStorage` namespaced by Firebase UID) and a hover/selection context card.
- `StreamingText.tsx` — full markdown renderer (headings, bold/italic, code blocks, links, lists, blockquotes, hr) plus the Claude-style "Thinking" indicator (pulsing orb + wave-motion dots) used while an agent is reasoning before its answer streams.
- `SourcePanel.tsx` — citation cards with real per-source SVG logos (Slack/Gmail/Drive/Jira/Zoom/Notion).
- `IntegrationGrid.tsx` / `IntegrationButton.tsx` — the 6-service OAuth connect UI, including Notion's manual-API-key fallback path.
- `ChatHistoryPanel.tsx` — session history sidebar (search/select/delete).
- `ConnectionStatus.tsx` — animated WebSocket connection indicator.
- `KairosLogo.tsx` — brand mark.

**Hooks** (`frontend/hooks/`): `useKairosChat.ts` owns the WebSocket lifecycle, message/source streaming, and session state; `useAuth.ts` owns Firebase auth (popup + redirect fallback, anonymous login, 50-min token refresh, simulation mode).

**Lib** (`frontend/lib/`): `websocket.ts` (singleton client, exponential-backoff reconnect), `firebase.ts` (defensive init), `api.ts` (REST client), `mcp-auth.ts` (remote MCP token helpers).

**Theming:** dark by default, toggled via `[data-theme]` on `:root` — all colors are `rgb(var(--...))` CSS variables (see `app/globals.css`), so components never hardcode a palette. `DecisionGraph` reads the computed variables at runtime and re-reads them on a `MutationObserver` watching `data-theme`.

## Key Design Decisions

**LLM calls never touch OpenAI or Anthropic directly** — `core/fireworks.py` is the only place that calls out to a model, always through an OpenAI-compatible client pointed at Fireworks (primary, satisfies the AMD hackathon requirement), Groq, or Gemini.

**Always stream** — WebSocket sends tokens as they arrive; `/query` is the only synchronous exception.

**Always show sources** — every `DecisionNode` carries `source_url`; the synthesis and live-data agents always cite it.

**Fail-closed multi-tenancy** — `memory.py`'s `semantic_search()`, `structured_search()`, and `hybrid_search()` all return `[]` immediately if called without a `user_id`, rather than falling back to a global query. `graph.py`'s auto-linker explicitly refuses to connect nodes across different `user_id`s. Any new memory-reading code path must take and enforce `user_id` — this is the property most worth protecting as the codebase grows.

**Dual memory, one file** — ChromaDB for semantic queries ("find decisions about vendor renewals"); the rest (`decisions`, `inventory`, `relations`, `user_conversations`, `user_profiles`, `oauth_tokens`, `mcp_oauth_*`) lives in one SQLite file at `config.SQLITE_PATH`. `memory.py`, `graph.py`, and `user_memory.py` all open the *same* file.

**Obsidian auto-sync** — `memory.store()` → `graph.add_decision(vault_path=..., user_id=...)` → writes only the changed `.md` file(s) into that user's `KAIROS_{user_id}/` folder plus the shared index. `memory.rebuild_obsidian()` forces a full re-export.

**Tokens are encrypted at rest** — `oauth_tokens.token_data` is Fernet-encrypted via `TOKEN_ENCRYPTION_KEY`; only falls back to plaintext when `DEBUG=true` and no key is configured.

**Inventory is a cheap pre-LLM cache** — every ingestion cycle writes raw item metadata (no LLM call) to the `inventory` table first, then only runs extraction on the capped, unprocessed subset. This is what lets `LiveDataAgent` answer instant "what do I have" questions without waiting on extraction.

## SQLite Schema

All tables live in one file (`config.SQLITE_PATH`, default `./kairos.db`):

```sql
-- core/memory.py + core/graph.py (shared table, JSON columns for participants/topics/metadata)
decisions (id, title, summary, date, participants, source, source_url, topics, outcome, raw_text, metadata, user_id)

-- core/memory.py — raw pre-LLM cache for instant "what do I have" queries
inventory (user_id, source, item_id, title, url, item_date, kind, snippet, fetched_at, processed,
           PRIMARY KEY (user_id, item_id))

-- core/graph.py — decision-to-decision edges
relations (from_id, to_id, relation_type)

-- api/routes/oauth.py — per-user, per-service encrypted OAuth grants
oauth_tokens (user_uid, service, token_data, connected_at)

-- core/user_memory.py — chat history + learned profile
user_conversations (user_id, session_id, role, content, timestamp, metadata)
user_profiles (user_id, display_name, department, role_context, frequent_topics, interaction_summary)

-- api/routes/mcp_oauth.py — RFC 7591 dynamic client registration for remote MCP
mcp_oauth_clients (...)
mcp_oauth_requests (...)
mcp_oauth_codes (...)
```

There is no separate `sources` / `people` / `projects` / `tags` table — those are inlined as JSON columns (`participants`, `topics`, `metadata`) on `decisions`.

## Environment Variables

All defined in `config.py`. Copy `.env.example` → `.env`. Key vars:

- **LLM (priority order):** `FIREWORKS_API_KEY` / `FIREWORKS_MODEL` (default `qwen3p7-plus`) / `FIREWORKS_MODEL_FAST` (default `llama-v3p3-70b-instruct`) — required for AMD hackathon compliance; `GROQ_API_KEY` / `GROQ_MODEL`; `GEMINI_API_KEY` / `GEMINI_MODEL` / `GEMINI_EMBED_MODEL` — fallback chain, all optional but recommended for resilience
- **Memory paths:** `CHROMA_PERSIST_DIR`, `SQLITE_PATH`, `OBSIDIAN_VAULT`
- **Security:** `TOKEN_ENCRYPTION_KEY` (Fernet key for stored OAuth tokens), `MCP_CONNECT_SECRET` (signs MCP tokens; also used as an oauth-state fallback secret), `FIREBASE_SERVICE_ACCOUNT` (JSON, or use `GOOGLE_APPLICATION_CREDENTIALS` / ADC)
- **Connectors:** `SLACK_BOT_TOKEN` / `SLACK_APP_TOKEN` / `SLACK_CLIENT_ID` / `SLACK_CLIENT_SECRET`; `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` / `GOOGLE_REFRESH_TOKEN` (Gmail + Drive share one grant); `ZOOM_ACCOUNT_ID` / `ZOOM_CLIENT_ID` / `ZOOM_CLIENT_SECRET`; `NOTION_CLIENT_ID` / `NOTION_CLIENT_SECRET`; `GITHUB_CLIENT_ID` / `GITHUB_CLIENT_SECRET` (real per-user OAuth, `repo read:user` scope); `JIRA_URL` / `JIRA_EMAIL` / `JIRA_API_TOKEN` / `JIRA_OWNER_UID` (global fallback credential) plus `JIRA_CLIENT_ID` / `JIRA_CLIENT_SECRET` (real per-user OAuth — code is complete, just needs these two values registered at developer.atlassian.com; currently unset in this deployment, so Jira falls back to the global credential for every user)
- **App:** `PORT` (8000), `HOST`, `DEBUG`, `FRONTEND_URL`, `BACKEND_URL`, `SEED_DEMO_DATA`, `DEMO_USER_ID`, `DEMO_LOGIN_EMAIL`
- **Ingestion tuning:** `SLACK_LOOKBACK_DAYS` / `EMAIL_LOOKBACK_DAYS` (30), `INGEST_INTERVAL_MINUTES` (12), `MAX_MESSAGES_PER_CHANNEL` (500), `MAX_EXTRACT_PER_CYCLE` (24), `EXTRACT_DELAY_SECONDS` (4) — throttle LLM calls per ingestion cycle to stay under provider TPM limits

Frontend (`frontend/.env.local`, all `NEXT_PUBLIC_*`): `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_WS_URL`, and the six `NEXT_PUBLIC_FIREBASE_*` config values.

## Current Status

All 8 connectors/agents (Slack, Gmail, Drive, Jira, Zoom, Notion, GitHub, plus meeting/Zoom transcription), dual-transport MCP, WebSocket streaming, the physics-based decision graph, and fail-closed multi-tenant isolation are implemented and live (see `docs/REMOTE_MCP.md` for the remote MCP model). Known open gaps:
- Per-user Jira OAuth is fully coded (`api/routes/oauth.py`'s `jira_start`/`jira_callback`, `connectors/jira_connector.py`'s cloud_id resolution + refresh tokens) but not live in this deployment — `JIRA_CLIENT_ID`/`JIRA_CLIENT_SECRET` were never registered at developer.atlassian.com, so Jira currently falls back to the single global `JIRA_OWNER_UID` credential for every user. Registering those and setting them in `.env` is the only remaining step, not a code change.
- Meeting transcription needs `openai-whisper` installed locally; it's intentionally excluded from the HF Docker image, so Zoom recordings list but don't transcribe in the hosted deployment.
- The MCP "Activity Monitor" panel's backend is real (core/mcp_telemetry.py logs every tool call on both transports, `GET /api/admin/mcp-activity` serves it, the dashboard fetches it), but the actual visual panel in the MCP tab's JSX needs to be (re)built — it was removed in a prior edit, leaving the fetch wired to state nothing currently renders.

## Non-Negotiables

- Never call OpenAI or Anthropic directly — always go through `core/fireworks.py`'s provider chain (Fireworks primary)
- Every answer cites sources (Slack link / email / doc / Notion page / etc.)
- Responses stream over WebSocket, never batch
- Dark theme by default throughout (light theme is a toggle, not the default)
- Docker must work before moving phases
- Demo data company: **Helios Tech**, only ever visible to `DEMO_LOGIN_EMAIL`
- Every memory read/write path must take `user_id` and fail closed without it — this is the multi-tenancy guarantee; do not regress it
