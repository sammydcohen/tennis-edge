import type { Metadata } from "next";

import { getRankings } from "@/lib/data";
import { RankingsBoard } from "./rankings-board";

export const metadata: Metadata = { title: "Rankings · Tennis Edge" };

export default function RankingsPage() {
  return (
    <div className="mx-auto max-w-6xl px-4 sm:px-6 pt-12">
      <p className="text-sm font-medium text-muted-foreground">Model ratings</p>
      <h1 className="mt-1 text-3xl sm:text-4xl font-semibold tracking-tight">Elo rankings</h1>
      <p className="mt-3 max-w-3xl text-muted-foreground leading-relaxed">
        The model&apos;s own ratings, updated after every match. Unlike official rankings, which count points from the last
        twelve months, Elo weighs who you beat. Beating a 2200-rated player is worth far more than beating a 1700. Only
        players active in the last six months are shown.
      </p>
      <RankingsBoard atp={getRankings("atp")} wta={getRankings("wta")} />
    </div>
  );
}
