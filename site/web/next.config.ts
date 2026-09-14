import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Next.js 16 blocks cross-origin dev resources by default; without this, opening the
  // dev server via 127.0.0.1 instead of localhost silently breaks client hydration/effects
  // (not just HMR) with no error surfaced. Add any other dev host/IP this is accessed from.
  allowedDevOrigins: ["localhost", "127.0.0.1"],
};

export default nextConfig;
