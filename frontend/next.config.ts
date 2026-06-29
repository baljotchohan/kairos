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
        source: "/mcp/:path*",
        destination: `${API_URL}/mcp/:path*`,
      },
      {
        source: "/.well-known/:path*",
        destination: `${API_URL}/.well-known/:path*`,
      },
    ];
  },
};

export default nextConfig;
