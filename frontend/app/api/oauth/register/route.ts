import { NextRequest, NextResponse } from "next/server";
import crypto from "crypto";

export async function POST(_req: NextRequest) {
  const client_id = crypto.randomBytes(16).toString("hex");

  return NextResponse.json(
    {
      client_id,
      client_id_issued_at: Math.floor(Date.now() / 1000),
      grant_types: ["authorization_code"],
      response_types: ["code"],
      token_endpoint_auth_method: "none",
    },
    { status: 201 }
  );
}
