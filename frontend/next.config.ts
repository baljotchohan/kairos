import type { NextConfig } from "next";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  output: "standalone",
  reactStrictMode: true,
  async rewrites() {
    return {
      beforeFiles: [
        // Discovery + metadata: served by Next.js (no secrets needed)
        {
          source: "/.well-known/oauth-authorization-server",
          destination: "/api/oauth/discovery",
        },
        // RFC 9728 — Claude.ai fetches this to find the authorization server
        {
          source: "/.well-known/oauth-protected-resource",
          destination: "/api/oauth/protected-resource",
        },
        // Client registration: served by Next.js (stateless, no SQLite)
        {
          source: "/oauth/register",
          destination: "/api/oauth/register",
        },
        // Authorization + token: served by Next.js stateless JWT routes.
        // These used to go to the HF Space backend (which has SQLite state), but that
        // caused "kairos returned an error when connecting" every time we pushed to HF
        // because the rebuild wipes SQLite — any in-flight code was gone by the time
        // Claude exchanged it for a token. Stateless signed JWTs have no such race.
        {
          source: "/oauth/authorize",
          destination: "/api/oauth/authorize",
        },
        {
          source: "/oauth/token",
          destination: "/api/oauth/token",
        },
        // MCP Bearer proxy: served by Next.js Edge function (proxies SSE to backend)
        {
          source: "/mcp",
          destination: "/api/mcp",
        },
      ],
      afterFiles: [
        // All other API and MCP URL-token calls go to the backend
        {
          source: "/api/:path((?!oauth|mcp).*)",
          destination: `${API_URL}/api/:path*`,
        },
        {
          source: "/mcp/:path*",
          destination: `${API_URL}/mcp/:path*`,
        },
      ],
      fallback: [],
    };
  },
};

export default nextConfig;
