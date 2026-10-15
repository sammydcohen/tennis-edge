# Tennis Edge site

Static Next.js 16 site (shadcn/ui on Base UI, Recharts, Tailwind 4) that presents the project's findings.

- Data comes from JSON written by `uv run python -m tennis_edge.export` into `public/data/`.
- `npm run dev` for local development; `npm run build` emits a fully static site to `out/`, hostable on Vercel, GitHub Pages or any static host.
- Pages: `/` findings, `/live` upcoming matches and pick tracker (fetched at runtime), `/rankings` Elo leaderboards.
- Chart colours follow a validated colourblind-safe palette (Elo blue, serve/return orange, LightGBM aqua, market grey), defined as CSS variables in `src/app/globals.css`.
