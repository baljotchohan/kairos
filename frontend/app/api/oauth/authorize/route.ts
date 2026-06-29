import { NextRequest, NextResponse } from "next/server";
import { signPayload } from "@/lib/mcp-auth";

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
