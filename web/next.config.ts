import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Fully static site: the Python pipeline writes JSON into public/data and
  // `next build` emits plain HTML/JS to out/, hostable anywhere.
  output: "export",
  trailingSlash: true,
  // GitHub Pages serves the site under /tennis-edge; the deploy workflow sets this.
  basePath: process.env.NEXT_PUBLIC_BASE_PATH ?? "",
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
