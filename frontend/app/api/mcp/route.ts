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

const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS, DELETE",
  "Access-Control-Allow-Headers": "Authorization, Content-Type, Accept, Mcp-Session-Id, Mcp-Protocol-Version",
  "Access-Control-Expose-Headers": "Mcp-Session-Id",
  "Access-Control-Max-Age": "86400",
};

function buildTargetUrl(token: string, searchParamsString: string): string {
  const query = searchParamsString ? `?${searchParamsString}` : "";
  return `${BACKEND_URL}/mcp/u/${token}${query}`;
}

function extractToken(req: NextRequest): string | null {
  const authHeader = req.headers.get("authorization") ?? "";
  const parts = authHeader.trim().split(/\s+/);
  if (parts.length === 2 && parts[0].toLowerCase() === "bearer") {
    let token = parts[1];
    if (token.startsWith('"') && token.endsWith('"')) {
      token = token.slice(1, -1);
    }
    return token;
  }
  return null;
}

function unauthorized(base: string, rawAuthHeader: string, extractedToken: string | null) {
  const resourceMetadata = `${base}/.well-known/oauth-protected-resource`;
  return NextResponse.json(
    { jsonrpc: "2.0", id: null, error: { code: -32001, message: "Bearer token required" } },
    {
      status: 401,
      headers: {
        "WWW-Authenticate": `Bearer realm="KAIROS", resource_metadata="${resourceMetadata}"`,
        "X-Debug-Auth-Header": rawAuthHeader || "none",
        "X-Debug-Token-Extracted": extractedToken || "none",
        ...CORS_HEADERS,
      },
    }
  );
}

function baseUrl(req: NextRequest): string {
  const proto = req.headers.get("x-forwarded-proto") ?? "https";
  const host = req.headers.get("x-forwarded-host") ?? req.headers.get("host") ?? "";
  return `${proto}://${host}`;
}

// OPTIONS — Handle CORS preflight requests
export async function OPTIONS() {
  return new NextResponse(null, {
    status: 204,
    headers: CORS_HEADERS,
  });
}

// POST — Proxy MCP messages to the backend URL-token endpoint
export async function POST(req: NextRequest) {
  const token = extractToken(req);
  if (!token) {
    return unauthorized(baseUrl(req), req.headers.get("authorization") ?? "", token);
  }

  const { searchParams } = new URL(req.url);
  const targetUrl = buildTargetUrl(token, searchParams.toString());
  try {
    const bodyText = await req.text();
    const reqHeaders: Record<string, string> = {
      "Content-Type": "application/json",
      "Accept": "application/json, text/event-stream",
    };
    const sessionId = req.headers.get("mcp-session-id");
    if (sessionId) reqHeaders["Mcp-Session-Id"] = sessionId;

    const protocolVersion = req.headers.get("mcp-protocol-version");
    if (protocolVersion) reqHeaders["Mcp-Protocol-Version"] = protocolVersion;

    const upstream = await fetch(targetUrl, {
      method: "POST",
      headers: reqHeaders,
      body: bodyText.length > 0 ? bodyText : undefined,
      cache: "no-store",
    });

    if (upstream.status === 202) {
      return new NextResponse(null, { 
        status: 202,
        headers: CORS_HEADERS,
      });
    }

    const responseBody = await upstream.arrayBuffer();
    const responseHeaders: Record<string, string> = { 
      ...CORS_HEADERS,
      "X-Debug-Upstream-Status": String(upstream.status)
    };
    for (const h of FORWARDED_RESPONSE_HEADERS) {
      const v = upstream.headers.get(h);
      if (v) responseHeaders[h] = v;
    }
    return new NextResponse(responseBody, { status: upstream.status, headers: responseHeaders });
  } catch (e) {
    return NextResponse.json(
      { jsonrpc: "2.0", id: null, error: { code: -32603, message: "Failed to reach KAIROS backend" } },
      { 
        status: 502,
        headers: {
          ...CORS_HEADERS,
          "X-Debug-Error": e instanceof Error ? e.message : String(e),
        },
      }
    );
  }
}

// GET — Proxy the backend's long-lived SSE stream to Claude
export async function GET(req: NextRequest) {
  const token = extractToken(req);
  if (!token) {
    return unauthorized(baseUrl(req), req.headers.get("authorization") ?? "", token);
  }

  const { searchParams } = new URL(req.url);
  const targetUrl = buildTargetUrl(token, searchParams.toString());
  const host = req.headers.get("x-forwarded-host") ?? req.headers.get("host") ?? "";
  const proto = req.headers.get("x-forwarded-proto") ?? "https";

  try {
    const upstream = await fetch(targetUrl, {
      method: "GET",
      headers: {
        "Accept": "text/event-stream",
        "Cache-Control": "no-cache",
        "x-forwarded-host": host,
        "x-forwarded-proto": proto,
      },
      cache: "no-store", // CRITICAL: Prevents Next.js from caching the SSE stream
    });

    if (!upstream.ok || !upstream.body) {
      return new NextResponse(null, { 
        status: upstream.status || 502,
        headers: {
          ...CORS_HEADERS,
          "X-Debug-Upstream-Status": String(upstream.status),
        },
      });
    }

    const responseHeaders = {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache, no-transform",
      "X-Accel-Buffering": "no",
      "X-Debug-Upstream-Status": String(upstream.status),
      ...CORS_HEADERS,
    };

    return new NextResponse(upstream.body, {
      status: 200,
      headers: responseHeaders,
    });
  } catch (e) {
    return new NextResponse(null, { 
      status: 502,
      headers: {
        ...CORS_HEADERS,
        "X-Debug-Error": e instanceof Error ? e.message : String(e),
      },
    });
  }
}

// DELETE — session cleanup
export async function DELETE(req: NextRequest) {
  const token = extractToken(req);
  if (!token) {
    return unauthorized(baseUrl(req), req.headers.get("authorization") ?? "", token);
  }
  const { searchParams } = new URL(req.url);
  const targetUrl = buildTargetUrl(token, searchParams.toString());
  return new NextResponse(null, { 
    status: 204,
    headers: CORS_HEADERS,
  });
}
