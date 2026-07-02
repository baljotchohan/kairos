import { NextRequest, NextResponse } from "next/server";
import crypto from "crypto";
import { signPayload } from "@/lib/mcp-auth";

export async function POST(req: NextRequest) {
  let body: Record<string, unknown> = {};
  try {
    body = await req.json();
  } catch {
    // no body or invalid JSON — proceed with defaults
  }

  const redirect_uris: string[] = Array.isArray(body.redirect_uris)
    ? (body.redirect_uris as string[])
    : [];

  // This endpoint is stateless (no SQLite reachable from the edge), so the
  // registered redirect_uris are encoded directly into the client_id as a
  // signed, tamper-proof payload. /oauth/authorize later decodes this same
  // client_id and requires the presented redirect_uri to be one of these —
  // otherwise dynamic client registration would let anyone reuse a known
  // client_id with an attacker-controlled redirect_uri (RFC 6749 §3.1.2.3).
  const client_id = signPayload({
    redirect_uris,
    nonce: crypto.randomBytes(8).toString("hex"),
  });

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
