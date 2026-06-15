import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Served by FastAPI at / (root)
  output: "export",
  // Dev: proxy API to FastAPI
  async rewrites() {
    if (process.env.NODE_ENV !== "development") return [];
    return [
      {
        source: "/api/:path*",
        destination: "http://127.0.0.1:8000/api/:path*",
      },
      {
        source: "/api-reference/:path*",
        destination: "http://127.0.0.1:8000/api-reference/:path*",
      },
      {
        source: "/openapi.json",
        destination: "http://127.0.0.1:8000/openapi.json",
      },
    ];
  },
};

export default nextConfig;
