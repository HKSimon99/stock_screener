import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  experimental: {
    viewTransition: true,
  },
  redirects: async () => [
    // /rankings is now a public route — no redirect needed (D5 decision)
    {
      source: "/alerts",
      destination: "/app/alerts",
      permanent: true,
    },
    {
      source: "/market-regime",
      destination: "/app/market-regime",
      permanent: true,
    },
    {
      source: "/instruments/:ticker",
      destination: "/app/search?q=:ticker",
      permanent: true,
    },
  ],
};

export default nextConfig;
