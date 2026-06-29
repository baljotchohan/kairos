# KAIROS Remote MCP — One-Click Connect

Connect Claude (Desktop / web / mobile), ChatGPT, or Cursor to **your own**
KAIROS organizational memory with a single URL. One deployed server serves every
user, scoped per-user — no cross-tenant leakage.

## How a user connects

1. Open KAIROS → **MCP Server** tab.
2. Copy your **personal connect URL**:
   ```
   https://<backend>/mcp/u/<your-token>
   ```
3. Paste it as a custom connector:
   - **Claude (web/mobile/desktop):** Settings → Connectors → *Add custom connector* → paste URL.
   - **ChatGPT:** Settings → Connectors (developer mode) → *Add* → paste URL.
   - **Cursor / Claude Desktop config:** copy the generated JSON:
     ```json
     { "mcpServers": { "kairos": { "url": "https://<backend>/mcp/u/<token>" } } }
     ```

The client then sees three tools — `get_context`, `store_context`,
`search_decisions` — all scoped to the connecting user's decisions.

## How it works

- **Transport:** minimal, spec-compliant **Streamable HTTP** (JSON-RPC 2.0 over
  HTTP POST) implemented in [`api/routes/mcp_remote.py`](../api/routes/mcp_remote.py).
  Methods: `initialize`, `tools/list`, `tools/call`, `ping`, notifications.
- **Auth / tenancy:** the token in the URL is an HMAC-signed credential
  ([`core/mcp_auth.py`](../core/mcp_auth.py)) encoding the user's Firebase uid.
  Every JSON-RPC call verifies it and scopes all memory reads/writes to that uid.
- **Local stdio** ([`mcp_server.py`](../mcp_server.py)) is unchanged for
  IDE/desktop use via `MCP_TENANT_ID`.

## Configuration

| Env var | Purpose |
|---------|---------|
| `MCP_CONNECT_SECRET` | **Set in production.** Stable HMAC key signing connect tokens. If unset, a deterministic fallback is derived (dev/demo only). |
| `BACKEND_URL` | Public base URL used to build the connect URL (e.g. the HF Space URL). |

## Security notes & the proper upgrade

The token-in-URL model is the pragmatic one-click path. The token is a bearer
credential, so the URL is **secret** (treat like an API key; rotate by changing
`MCP_CONNECT_SECRET`). There is no per-token revocation list yet.

The production-grade upgrade is the **MCP authorization spec**: OAuth 2.1 +
Dynamic Client Registration (RFC 7591), Protected Resource Metadata (RFC 9728),
and Authorization Server Metadata (RFC 8414), bridged to Firebase so the client
does a real OAuth handshake instead of carrying a token in the URL. The transport
and per-request tenant-resolution layer here already isolate the seam where that
slots in (`verify_mcp_token` → `user_id`).
