import type { NextConfig } from "next";
const nextConfig: NextConfig = {
  // Vercel manages its own output packaging; Docker uses Next's standalone
  // server artifact for the existing production container.
  output: process.env.VERCEL ? undefined : "standalone",
  poweredByHeader: false,
  experimental: {
    // The Docker volume survives restarts; keep each dev HMR graph fresh.
    turbopackFileSystemCacheForDev: false,
  },
  async headers() {
    const privateHeaders = [
      "/admin/:path*",
      "/api/admin/:path*",
      "/dashboard/:path*",
      "/api/account/:path*",
      "/login",
      "/register",
    ].map((source) => ({
      source,
      headers: [
        { key: "X-Frame-Options", value: "DENY" },
        { key: "X-Content-Type-Options", value: "nosniff" },
        { key: "Referrer-Policy", value: "same-origin" },
        { key: "Cache-Control", value: "private, no-store" },
      ],
    }));
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Referrer-Policy", value: "same-origin" },
          {
            key: "Permissions-Policy",
            value: "camera=(), microphone=(), geolocation=()",
          },
        ],
      },
      ...privateHeaders,
    ];
  },
};
export default nextConfig;
