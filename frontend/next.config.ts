import type { NextConfig } from "next";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  output: "standalone",
  reactStrictMode: true,
  async rewrites() {
    return {
      beforeFiles: [
        // OAuth served entirely by Next.js (no backend needed)
        {
          source: "/.well-known/oauth-authorization-server",
          destination: "/api/oauth/discovery",
        },
        {
          source: "/oauth/register",
          destination: "/api/oauth/register",
        },
        {
          source: "/oauth/authorize",
          destination: "/api/oauth/authorize",
        },
        {
          source: "/oauth/token",
          destination: "/api/oauth/token",
        },
        // MCP Bearer endpoint served by Next.js proxy
        {
          source: "/mcp",
          destination: "/api/mcp",
        },
      ],
      afterFiles: [
        // All other API and MCP (URL-token) calls go to the backend
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
