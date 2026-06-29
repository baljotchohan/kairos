import type { NextConfig } from "next";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  output: "standalone",
  reactStrictMode: true,
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${API_URL}/api/:path*`,
      },
      {
        source: "/mcp",
        destination: `${API_URL}/mcp`,
      },
      {
        source: "/mcp/:path*",
        destination: `${API_URL}/mcp/:path*`,
      },
      // MCP OAuth 2.0 endpoints — required by Claude.ai connector platform
      {
        source: "/.well-known/oauth-authorization-server",
        destination: `${API_URL}/.well-known/oauth-authorization-server`,
      },
      {
        source: "/oauth/authorize",
        destination: `${API_URL}/oauth/authorize`,
      },
      {
        source: "/oauth/token",
        destination: `${API_URL}/oauth/token`,
      },
      {
        source: "/oauth/register",
        destination: `${API_URL}/oauth/register`,
      },
    ];
  },
};

export default nextConfig;
