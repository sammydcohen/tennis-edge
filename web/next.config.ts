import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Fully static site: the Python pipeline writes JSON into public/data and
  // `next build` emits plain HTML/JS to out/, hostable anywhere.
  output: "export",
  trailingSlash: true,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
