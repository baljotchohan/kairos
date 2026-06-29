import { NextRequest, NextResponse } from "next/server";

export async function POST(req: NextRequest) {
  const authHeader = req.headers.get("authorization") ?? "";
  const token = authHeader.startsWith("Bearer ") ? authHeader.slice(7).trim() : null;

  if (!token) {
    return NextResponse.json(
      { jsonrpc: "2.0", id: null, error: { code: -32001, message: "Bearer token required" } },
      { status: 401, headers: { "WWW-Authenticate": 'Bearer realm="KAIROS"' } }
    );
  }

  const backendUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
  // Forward to backend's URL-token endpoint (compatible with all backend code versions)
  const targetUrl = `${backendUrl}/mcp/u/${token}`;

  try {
    // Read as text — arrayBuffer() loses body through Next.js beforeFiles rewrites
    const bodyText = await req.text();

    const upstream = await fetch(targetUrl, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Accept": "application/json",
      },
      body: bodyText.length > 0 ? bodyText : undefined,
    });

    // 202 No Content = MCP notification acknowledged
    if (upstream.status === 202) {
      return new NextResponse(null, { status: 202 });
    }

    const responseBody = await upstream.arrayBuffer();
    const responseContentType =
      upstream.headers.get("content-type") ?? "application/json";

    return new NextResponse(responseBody, {
      status: upstream.status,
      headers: { "Content-Type": responseContentType },
    });
  } catch (err) {
    console.error("[/api/mcp] upstream fetch failed:", err);
    return NextResponse.json(
      { jsonrpc: "2.0", id: null, error: { code: -32603, message: "Failed to reach KAIROS backend" } },
      { status: 502 }
    );
  }
}

export async function GET() {
  return new NextResponse(null, { status: 405 });
}
