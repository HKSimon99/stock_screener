import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  redirects: async () => [
    // Old root routes → /app/* authenticated equivalents (301 permanent)
    {
      source: "/rankings",
      destination: "/app/rankings",
      permanent: true,
    },
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
