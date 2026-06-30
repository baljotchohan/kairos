import { NextRequest, NextResponse } from "next/server";
import { verifyFirebaseToken, verifyPayload, signPayload } from "@/lib/mcp-auth";

const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface SessionPayload {
  client_id: string;
  redirect_uri: string;
  code_challenge: string;
  code_challenge_method: string;
  state: string;
  exp: number;
}

export async function POST(req: NextRequest) {
  let body: { firebase_token?: string; session?: string };
  try {
    body = await req.json();
  } catch {
    return NextResponse.json(
      { error: "invalid_request", error_description: "Invalid JSON body" },
      { status: 400 }
    );
  }

  const { firebase_token, session } = body;

  if (!firebase_token || !session) {
    return NextResponse.json(
      { error: "invalid_request", error_description: "firebase_token and session are required" },
      { status: 400 }
    );
  }

  const uid = await verifyFirebaseToken(firebase_token);
  if (!uid) {
    return NextResponse.json(
      { error: "access_denied", error_description: "Firebase token verification failed" },
      { status: 401 }
    );
  }

  const sessionPayload = verifyPayload<SessionPayload>(session);
  if (!sessionPayload) {
    return NextResponse.json(
      { error: "invalid_request", error_description: "Invalid or tampered session" },
      { status: 400 }
    );
  }

  const now = Math.floor(Date.now() / 1000);
  if (sessionPayload.exp < now) {
    return NextResponse.json(
      { error: "invalid_request", error_description: "Session expired" },
      { status: 400 }
    );
  }

  // Get the MCP token from the backend (which holds MCP_CONNECT_SECRET and signs it).
  // Embedding it in the code here means the token endpoint never needs MCP_CONNECT_SECRET.
  let mcp_token: string;
  try {
    const connResp = await fetch(`${BACKEND_URL}/api/v1/mcp/connection`, {
      headers: { Authorization: `Bearer ${firebase_token}` },
    });
    if (!connResp.ok) {
      const err = await connResp.json().catch(() => ({}));
      return NextResponse.json(
        { error: "server_error", error_description: `Backend refused to mint token: ${connResp.status} ${err?.detail ?? ""}` },
        { status: 502 }
      );
    }
    const connData = await connResp.json();
    mcp_token = connData.token as string;
    if (!mcp_token) throw new Error("Backend returned no token");
  } catch (e) {
    return NextResponse.json(
      { error: "server_error", error_description: `Could not mint MCP token: ${e}` },
      { status: 502 }
    );
  }

  // Sign the code with PKCE + pre-minted token (10-minute TTL).
  // Token endpoint just verifies PKCE and returns mcp_token — no cross-system secret needed.
  const code = signPayload({
    uid,
    mcp_token,
    redirect_uri: sessionPayload.redirect_uri,
    code_challenge: sessionPayload.code_challenge,
    state: sessionPayload.state,
    exp: now + 600,
  });

  return NextResponse.json({
    code,
    redirect_uri: sessionPayload.redirect_uri,
    state: sessionPayload.state,
  });
}
