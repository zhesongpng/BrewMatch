import type { NextConfig } from "next";
import path from "node:path";

const nextConfig: NextConfig = {
  // Pin the workspace root to this app so Next does not infer it from an
  // unrelated lockfile higher up the filesystem (the BrewMatch repo lives
  // under a path that has other lockfiles above it).
  turbopack: {
    root: path.resolve(__dirname),
  },
};

export default nextConfig;
