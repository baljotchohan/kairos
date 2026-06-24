---
title: KAIROS Backend
emoji: 🧠
colorFrom: indigo
colorTo: purple
sdk: docker
pinned: false
---

# KAIROS — Company Organizational Memory OS

> "Every company forgets why it made its decisions. KAIROS never does."

Built for the **AMD Developer Hackathon ACT II** by [Baljot / Antigravity](https://github.com/baljotchohan).

## What It Does

KAIROS connects to a company's Slack, Gmail, Google Drive, Jira, and Zoom — reads everything, extracts every decision and its context, and stores it permanently. Anyone can ask natural language questions and get the full decision history with sources in seconds.

## Quick Start

```bash
cp .env.example .env
# Fill in FIREWORKS_API_KEY and connector tokens

docker-compose up --build
# Backend: http://localhost:8000
# Frontend: http://localhost:3000
```

## Architecture

```
Connectors → Agents → Core (Memory + Graph) → API + MCP + Frontend

5 parallel agents (LangGraph):
  Slack Agent     → reads channels, extracts decisions
  Email Agent     → Gmail threads, approvals, escalations
  Drive Agent     → Google Docs, meeting notes, proposals
  Meeting Agent   → Zoom recordings via Whisper transcription
  Synthesis Agent → orchestrates queries, builds unified answer

Memory layers:
  ChromaDB  → semantic vector search ("find decisions about AWS")
  SQLite    → structured search ("decisions by John in Q3 2021")
  NetworkX  → decision graph (links by topic, person, project)
```

## AI Stack (AMD Hardware via Fireworks AI)

- **LLM:** `accounts/fireworks/models/qwen2p5-72b-instruct`
- **Embeddings:** `nomic-ai/nomic-embed-text-v1.5`
- **Speech:** `whisper-v3`

## MCP Server

Expose KAIROS as an MCP tool for Claude Desktop / Claude Code:

```bash
python mcp_server.py
```

Tools: `get_context`, `store_context`, `search_decisions`

## Environment Variables

See [.env.example](.env.example) for all required variables.

## License

MIT
