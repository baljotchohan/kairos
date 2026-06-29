import { NextRequest, NextResponse } from "next/server";
import crypto from "crypto";

export async function POST(req: NextRequest) {
  let body: Record<string, unknown> = {};
  try {
    body = await req.json();
  } catch {
    // no body or invalid JSON — proceed with defaults
  }

  const client_id = crypto.randomBytes(16).toString("hex");
  const redirect_uris: string[] = Array.isArray(body.redirect_uris)
    ? (body.redirect_uris as string[])
    : [];

  // RFC 7591 §3.2.1: echo back all client metadata supplied in the request
  return NextResponse.json(
    {
      client_id,
      client_id_issued_at: Math.floor(Date.now() / 1000),
      redirect_uris,
      grant_types: ["authorization_code"],
      response_types: ["code"],
      token_endpoint_auth_method: "none",
      scope: typeof body.scope === "string" ? body.scope : "mcp",
    },
    { status: 201 }
  );
}
