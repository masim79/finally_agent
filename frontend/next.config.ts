import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // FastAPI serves the built site as plain static files from /app/static.
  output: "export",
  images: { unoptimized: true },
  trailingSlash: true,
};

export default nextConfig;
