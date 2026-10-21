import type { NextConfig } from "next";

// Rewrites are evaluated at build time and serialised into the build manifest, so
// this value cannot be changed at runtime. It defaults to localhost for
// `next dev`; the Docker image passes BACKEND_INTERNAL_URL at build time,
// because a container cannot reach the backend through its own localhost.
const backendInternalUrl =
  process.env.BACKEND_INTERNAL_URL ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  output: process.env.NODE_ENV === "production" ? "standalone" : undefined,
  allowedDevOrigins: ['127.0.0.1'],
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: `${backendInternalUrl}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
