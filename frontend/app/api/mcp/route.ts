import { NextRequest, NextResponse } from "next/server";

export async function POST(req: NextRequest) {
  const authHeader = req.headers.get("authorization") ?? "";
  const token = authHeader.startsWith("Bearer ") ? authHeader.slice(7) : null;

  if (!token) {
    return NextResponse.json(
      { error: "unauthorized", error_description: "Missing Bearer token" },
      { status: 401 }
    );
  }

  const backendUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
  const targetUrl = `${backendUrl}/mcp/u/${encodeURIComponent(token)}`;

  try {
    const body = await req.arrayBuffer();
    const contentType = req.headers.get("content-type") ?? "application/json";

    const upstream = await fetch(targetUrl, {
      method: "POST",
      headers: {
        "Content-Type": contentType,
      },
      body: body,
    });

    const responseBody = await upstream.arrayBuffer();
    const responseContentType =
      upstream.headers.get("content-type") ?? "application/json";

    return new NextResponse(responseBody, {
      status: upstream.status,
      headers: {
        "Content-Type": responseContentType,
      },
    });
  } catch (err) {
    console.error("[/api/mcp] upstream fetch failed:", err);
    return NextResponse.json(
      { error: "upstream_error", error_description: "Failed to reach KAIROS backend" },
      { status: 502 }
    );
  }
}

export async function GET() {
  return new NextResponse(null, { status: 405 });
}
