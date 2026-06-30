import { NextRequest, NextResponse } from "next/server";
import { verifyPayload } from "@/lib/mcp-auth";
import crypto from "crypto";

interface AuthCodePayload {
  uid: string;
  mcp_token: string;
  redirect_uri: string;
  code_challenge: string;
  state: string;
  exp: number;
}

function stripPadding(s: string): string {
  return s.replace(/=+$/, "");
}

export async function POST(req: NextRequest) {
  let grant_type: string | null = null;
  let code: string | null = null;
  let code_verifier: string | null = null;

  const contentType = req.headers.get("content-type") ?? "";

  if (contentType.includes("application/x-www-form-urlencoded")) {
    const text = await req.text();
    const params = new URLSearchParams(text);
    grant_type = params.get("grant_type");
    code = params.get("code");
    code_verifier = params.get("code_verifier");
  } else {
    try {
      const body = await req.json();
      grant_type = body.grant_type ?? null;
      code = body.code ?? null;
      code_verifier = body.code_verifier ?? null;
    } catch {
      return NextResponse.json(
        { error: "invalid_request", error_description: "Invalid request body" },
        { status: 400 }
      );
    }
  }

  if (grant_type !== "authorization_code") {
    return NextResponse.json(
      { error: "unsupported_grant_type" },
      { status: 400 }
    );
  }

  if (!code) {
    return NextResponse.json(
      { error: "invalid_request", error_description: "code is required" },
      { status: 400 }
    );
  }

  const payload = verifyPayload<AuthCodePayload>(code);
  if (!payload) {
    return NextResponse.json(
      { error: "invalid_grant", error_description: "Invalid or tampered authorization code" },
      { status: 400 }
    );
  }

  const now = Math.floor(Date.now() / 1000);
  if (payload.exp < now) {
    return NextResponse.json(
      { error: "invalid_grant", error_description: "Authorization code expired" },
      { status: 400 }
    );
  }

  // Verify PKCE when code_verifier is present.
  // SHA256(code_verifier) base64url (no padding) must match stored code_challenge.
  if (payload.code_challenge && code_verifier) {
    const computed = stripPadding(
      crypto.createHash("sha256").update(code_verifier).digest("base64url")
    );
    const stored = stripPadding(payload.code_challenge);
    if (computed !== stored) {
      return NextResponse.json(
        { error: "invalid_grant", error_description: "PKCE verification failed" },
        { status: 400 }
      );
    }
  }

  // The MCP token was pre-minted by the backend (which holds MCP_CONNECT_SECRET).
  // No cross-system secret needed here.
  return NextResponse.json({
    access_token: payload.mcp_token,
    token_type: "bearer",
    expires_in: 31536000,
  });
}
