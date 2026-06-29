import { NextRequest, NextResponse } from "next/server";
import { verifyFirebaseToken, verifyPayload, signPayload } from "@/lib/mcp-auth";

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

  const code = signPayload({
    uid,
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
