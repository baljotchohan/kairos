import { NextRequest, NextResponse } from "next/server";

// RFC 9728 — OAuth 2.0 Protected Resource Metadata
// Claude.ai fetches this (via /.well-known/oauth-protected-resource) to discover
// which authorization server protects this MCP resource.
export async function GET(req: NextRequest) {
  const proto = req.headers.get("x-forwarded-proto") ?? "https";
  const host =
    req.headers.get("x-forwarded-host") ?? req.headers.get("host") ?? "";
  const base = `${proto}://${host}`;

  return NextResponse.json({
    resource: base,
    authorization_servers: [base],
    bearer_methods_supported: ["header"],
    resource_documentation: "https://modelcontextprotocol.io",
  });
}
