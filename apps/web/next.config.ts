import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  allowedDevOrigins: ["127.0.0.1", "localhost"],
  async rewrites() {
    const apiInternal = process.env.OPENMUSE_API_INTERNAL || "http://127.0.0.1:8000";
    return [{
      source: "/api/:path*",
      destination: `${apiInternal}/api/:path*`,
    }];
  },
};

export default nextConfig;
