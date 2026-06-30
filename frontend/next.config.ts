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
        {
          source: "/oauth/authorize",
          destination: "/api/oauth/authorize",
        },
        {
          source: "/oauth/token",
          destination: "/api/oauth/token",
        },
        // MCP Bearer and URL-token proxy: served by Next.js Edge function (proxies SSE to backend)
        {
          source: "/mcp",
          destination: "/api/mcp",
        },
        {
          source: "/mcp/:path*",
          destination: "/api/mcp",
        },
      ],
      afterFiles: [
        // Exclude local API routes from being proxied to the backend
        {
          source: "/api/oauth/:path*",
          destination: "/api/oauth/:path*",
        },
        {
          source: "/api/mcp",
          destination: "/api/mcp",
        },
        // All other API calls go to the backend
        {
          source: "/api/:path*",
          destination: `${API_URL}/api/:path*`,
        },
      ],
      fallback: [],
    };
  },
};

export default nextConfig;
