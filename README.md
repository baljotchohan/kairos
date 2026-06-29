---
title: KAIROS Backend
emoji: 🧠
colorFrom: indigo
colorTo: purple
sdk: docker
app_port: 7860
pinned: false
license: mit
short_description: Company Organizational Memory OS — AMD Hackathon ACT II
---

# KAIROS — Company Organizational Memory OS

> "Every company forgets why it made its decisions. KAIROS never does."

FastAPI backend for KAIROS. Exposes REST + WebSocket API for the Next.js frontend.

## Environment Variables (set in HF Space Settings → Variables)

| Variable | Description |
|---|---|
| `FIREWORKS_API_KEY` | Fireworks AI API key (AMD hardware models) |
| `GROQ_API_KEY` | Groq API key (fast completions) |
| `GEMINI_API_KEY` | Gemini API key (embeddings) |
| `FRONTEND_URL` | Your Vercel frontend URL e.g. `https://kairos-memory-os.vercel.app` |
| `SLACK_BOT_TOKEN` | Slack bot token (optional) |
| `SLACK_APP_TOKEN` | Slack socket mode token (optional) |
| `GOOGLE_CLIENT_ID` | Google OAuth client ID (optional) |
| `GOOGLE_CLIENT_SECRET` | Google OAuth secret (optional) |
| `GOOGLE_REFRESH_TOKEN` | Google refresh token (optional) |

## API Endpoints

- `GET /health` — health check
- `POST /api/v1/query` — query organizational memory
- `POST /api/v1/ingest` — trigger ingestion
- `WS /ws` — WebSocket for real-time streaming
- `GET /mcp` — MCP server endpoint
