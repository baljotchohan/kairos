import { NextRequest, NextResponse } from "next/server";
import crypto from "crypto";
import { verifyPayload, mintMcpToken } from "@/lib/mcp-auth";

interface AuthCodePayload {
  uid: string;
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

  if (!code || !code_verifier) {
    return NextResponse.json(
      { error: "invalid_request", error_description: "code and code_verifier are required" },
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

  // Verify PKCE: SHA256(code_verifier) base64url (no padding) must match stored code_challenge
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

  const access_token = mintMcpToken(payload.uid);

  return NextResponse.json({
    access_token,
    token_type: "bearer",
    expires_in: 31536000,
  });
}
