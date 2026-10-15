import type { Metadata } from "next";

import { LiveBoard } from "./live-board";

export const metadata: Metadata = { title: "Live matches · Tennis Edge" };

export default function LivePage() {
  return (
    <div className="mx-auto max-w-6xl px-4 sm:px-6 pt-12">
      <p className="text-sm font-medium text-muted-foreground">Paper trading</p>
      <h1 className="mt-1 text-3xl sm:text-4xl font-semibold tracking-tight">Live matches</h1>
      <p className="mt-3 max-w-3xl text-muted-foreground leading-relaxed">
        Upcoming ATP and WTA matches with the model&apos;s win probability next to the market&apos;s. When they disagree by
        more than 3 points, the pick is logged at the current price. Once the match starts, it&apos;s graded on whether
        the price moved its way. Nothing here is betting advice: so far the model has no proven edge.
      </p>
      <LiveBoard />
    </div>
  );
}
