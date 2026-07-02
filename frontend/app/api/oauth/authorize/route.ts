import { NextRequest, NextResponse } from "next/server";
import { signPayload, verifyPayload } from "@/lib/mcp-auth";

interface ClientPayload {
  redirect_uris: string[];
  nonce: string;
}

export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url);
  const client_id = searchParams.get("client_id") ?? "";
  const redirect_uri = searchParams.get("redirect_uri") ?? "";
  const code_challenge = searchParams.get("code_challenge") ?? "";
  const code_challenge_method = searchParams.get("code_challenge_method") ?? "S256";
  const state = searchParams.get("state") ?? "";
  const response_type = searchParams.get("response_type") ?? "";

  if (response_type !== "code") {
    return NextResponse.json(
      { error: "unsupported_response_type" },
      { status: 400 }
    );
  }

  if (!redirect_uri) {
    return NextResponse.json(
      { error: "invalid_request", error_description: "redirect_uri is required" },
      { status: 400 }
    );
  }

  if (!code_challenge) {
    return NextResponse.json(
      { error: "invalid_request", error_description: "code_challenge (PKCE) is required" },
      { status: 400 }
    );
  }

  // RFC 6749 §3.1.2.3 — redirect_uri MUST match one registered for this
  // client_id at /oauth/register. client_id is itself a signed payload
  // (see register/route.ts) encoding the redirect_uris that were registered
  // for it, since this edge route has no database to look them up in.
  // Without this check, client_ids aren't secret, so an attacker could reuse
  // a known client_id with their OWN redirect_uri, phish a real user into
  // signing in here, and have the resulting authorization code delivered to
  // an attacker-controlled origin — full access to that user's KAIROS data.
  const client = verifyPayload<ClientPayload>(client_id);
  if (!client || !Array.isArray(client.redirect_uris)) {
    return NextResponse.json(
      { error: "invalid_client", error_description: "Unknown or invalid client_id — register via /oauth/register first" },
      { status: 400 }
    );
  }
  if (!client.redirect_uris.includes(redirect_uri)) {
    return NextResponse.json(
      { error: "invalid_request", error_description: "redirect_uri does not match any URI registered for this client_id" },
      { status: 400 }
    );
  }

  const exp = Math.floor(Date.now() / 1000) + 900; // 15 min
  const session = signPayload({
    client_id,
    redirect_uri,
    code_challenge,
    code_challenge_method,
    state,
    exp,
  });

  const host = req.headers.get("x-forwarded-host") ?? req.headers.get("host") ?? "localhost:3000";
  const proto = req.headers.get("x-forwarded-proto") ?? "https";
  const loginUrl = `${proto}://${host}/oauth/login?session=${encodeURIComponent(session)}`;

  return NextResponse.redirect(loginUrl, 302);
}
