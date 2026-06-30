import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// Headers the backend sends that Claude.ai / ChatGPT need to see
const FORWARDED_RESPONSE_HEADERS = [
  "content-type",
  "mcp-session-id",
  "cache-control",
  "x-request-id",
];

function buildTargetUrl(token: string): string {
  return `${BACKEND_URL}/mcp/u/${token}`;
}

function extractToken(req: NextRequest): string | null {
  const authHeader = req.headers.get("authorization") ?? "";
  return authHeader.startsWith("Bearer ") ? authHeader.slice(7).trim() : null;
}

function unauthorized(base: string) {
  const resourceMetadata = `${base}/.well-known/oauth-protected-resource`;
  return NextResponse.json(
    { jsonrpc: "2.0", id: null, error: { code: -32001, message: "Bearer token required" } },
    {
      status: 401,
      headers: {
        "WWW-Authenticate": `Bearer realm="KAIROS", resource_metadata="${resourceMetadata}"`,
      },
    }
  );
}

function baseUrl(req: NextRequest): string {
  const proto = req.headers.get("x-forwarded-proto") ?? "https";
  const host = req.headers.get("x-forwarded-host") ?? req.headers.get("host") ?? "";
  return `${proto}://${host}`;
}

export async function POST(req: NextRequest) {
  const token = extractToken(req);
  if (!token) return unauthorized(baseUrl(req));

  const targetUrl = buildTargetUrl(token);
  try {
    const bodyText = await req.text();
    const reqHeaders: Record<string, string> = {
      "Content-Type": "application/json",
      "Accept": "application/json, text/event-stream",
    };
    const sessionId = req.headers.get("mcp-session-id");
    if (sessionId) reqHeaders["Mcp-Session-Id"] = sessionId;

    const upstream = await fetch(targetUrl, {
      method: "POST",
      headers: reqHeaders,
      body: bodyText.length > 0 ? bodyText : undefined,
    });

    if (upstream.status === 202) return new NextResponse(null, { status: 202 });

    const responseBody = await upstream.arrayBuffer();
    const responseHeaders: Record<string, string> = {};
    for (const h of FORWARDED_RESPONSE_HEADERS) {
      const v = upstream.headers.get(h);
      if (v) responseHeaders[h] = v;
    }
    return new NextResponse(responseBody, { status: upstream.status, headers: responseHeaders });
  } catch (err) {
    console.error("[/api/mcp POST] upstream fetch failed:", err);
    return NextResponse.json(
      { jsonrpc: "2.0", id: null, error: { code: -32603, message: "Failed to reach KAIROS backend" } },
      { status: 502 }
    );
  }
}

// GET — per MCP Streamable HTTP spec §3.2.1, returning 405 signals POST-only mode.
// Claude.ai and ChatGPT both fall back to stateless POST request-response automatically.
export async function GET(req: NextRequest) {
  const token = extractToken(req);
  if (!token) return unauthorized(baseUrl(req));
  return new NextResponse(null, {
    status: 405,
    headers: { "Allow": "POST, DELETE" },
  });
}

// DELETE for session cleanup (some MCP clients)
export async function DELETE(req: NextRequest) {
  const token = extractToken(req);
  if (!token) return unauthorized(baseUrl(req));
  return new NextResponse(null, { status: 204 });
}
