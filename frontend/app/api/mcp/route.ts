// Edge Runtime: no serverless timeout, supports long-lived SSE streaming.
// Required so the GET handler can proxy the backend's keepalive SSE stream
// without Vercel closing it after 25s (which causes Claude.ai to disconnect).
export const runtime = "edge";

import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

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

// POST — proxy MCP messages from Claude.ai to the backend URL-token endpoint.
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
  } catch {
    return NextResponse.json(
      { jsonrpc: "2.0", id: null, error: { code: -32603, message: "Failed to reach KAIROS backend" } },
      { status: 502 }
    );
  }
}

// GET — proxy the backend's long-lived SSE stream to Claude.ai.
//
// Claude.ai uses HTTP+SSE transport: it sends GET first to establish the SSE
// channel, reads the `endpoint` event (the URL to POST messages to), then keeps
// the SSE open for server-initiated messages and keepalive pings.
//
// The backend's GET /mcp/u/{token} sends:
//   event: endpoint
//   data: https://kairos-coral-nine.vercel.app/mcp/u/{token}?session_id=XXX
// then `: ping` every 15 s.
//
// Why this broke before:
//  - Returning 405 → Claude never got the endpoint URL → "error when connecting"
//  - Synthetic SSE that closes immediately → Claude saw the SSE drop → disconnected
//  - Edge Runtime is required so the stream is not killed by the 25 s serverless timeout
export async function GET(req: NextRequest) {
  const token = extractToken(req);
  if (!token) return unauthorized(baseUrl(req));

  const targetUrl = buildTargetUrl(token);
  const host = req.headers.get("x-forwarded-host") ?? req.headers.get("host") ?? "";
  const proto = req.headers.get("x-forwarded-proto") ?? "https";

  try {
    const upstream = await fetch(targetUrl, {
      method: "GET",
      headers: {
        "Accept": "text/event-stream",
        "Cache-Control": "no-cache",
        // Pass forwarding headers so the backend builds the correct endpoint URL
        // (uses kairos-coral-nine.vercel.app, not baljot07-kairos-backend.hf.space)
        "x-forwarded-host": host,
        "x-forwarded-proto": proto,
      },
    });

    if (!upstream.ok || !upstream.body) {
      return new NextResponse(null, { status: upstream.status || 502 });
    }

    // Stream the SSE body directly — Edge Runtime has no timeout so the connection
    // stays alive as long as Claude.ai keeps it open.
    return new NextResponse(upstream.body, {
      status: 200,
      headers: {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache, no-transform",
        "X-Accel-Buffering": "no",
      },
    });
  } catch {
    return new NextResponse(null, { status: 502 });
  }
}

// DELETE — session cleanup (some MCP clients send this on disconnect)
export async function DELETE(req: NextRequest) {
  const token = extractToken(req);
  if (!token) return unauthorized(baseUrl(req));
  return new NextResponse(null, { status: 204 });
}
