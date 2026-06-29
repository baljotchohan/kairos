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
        // Client registration: served by Next.js (no secrets needed)
        {
          source: "/oauth/register",
          destination: "/api/oauth/register",
        },
        // MCP Bearer proxy: served by Next.js (proxies to backend URL-token endpoint)
        {
          source: "/mcp",
          destination: "/api/mcp",
        },
      ],
      afterFiles: [
        // authorize + token go to backend — backend has MCP_CONNECT_SECRET + SQLite state
        // so we don't need to set MCP_CONNECT_SECRET in Vercel at all.
        {
          source: "/oauth/authorize",
          destination: `${API_URL}/oauth/authorize`,
        },
        {
          source: "/oauth/token",
          destination: `${API_URL}/oauth/token`,
        },
        // All other API and MCP URL-token calls go to the backend
        {
          source: "/api/:path*",
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
