"use client";

import { useEffect, useMemo, useState } from "react";
import { ArrowDownRight, ArrowUpRight, CircleCheck, CircleX, Clock, Info, Minus, Radio } from "lucide-react";
import { cn } from "cn";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { pct } from "@/lib/format";
import type { Tracker, Upcoming } from "@/lib/types";

type Filter = "all" | "atp" | "wta";

function startsIn(iso: string) {
  const mins = Math.round((new Date(iso + "Z").getTime() - Date.now()) / 60000);
  if (mins < 60) return `in ${Math.max(mins, 0)} min`;
  if (mins < 48 * 60) return `in ${Math.round(mins / 60)} h`;
  return `in ${Math.round(mins / 1440)} days`;
}

function localTime(iso: string) {
  return new Date(iso + "Z").toLocaleString(undefined, { weekday: "short", hour: "numeric", minute: "2-digit" });
}

function ProbRow({ label, p1, color }: { label: string; p1: number; color: string }) {
  const left = Math.round(p1 * 100); // round once so both sides always sum to 100%
  return (
    <div className="grid grid-cols-[4.5rem_2.75rem_1fr_2.75rem] items-center gap-2 text-xs">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-mono tabular-nums text-right">{left}%</span>
      <div className="flex h-2 overflow-hidden rounded-full bg-muted">
        <div className="h-full rounded-l-full" style={{ width: `${p1 * 100}%`, background: color }} />
        <div className="h-full w-0.5 bg-card" />
      </div>
      <span className="font-mono tabular-nums">{100 - left}%</span>
    </div>
  );
}

function MatchCard({ m: raw }: { m: Upcoming }) {
  const unknown = !raw.known_1 || !raw.known_2;
  // Matches with a player the model has never seen are shown but never picked or logged.
  const m = unknown ? { ...raw, pick: null } : raw;
  const move = m.market_open_p1 == null ? null : (m.reference_p1 - m.market_open_p1) * 100;
  const pickIs1 = m.pick === m.player_1;
  const pickEdge = m.pick ? Math.abs(m.edge_1) * 100 : 0;
  return (
    <Card size="sm" className={cn(m.pick && "ring-[var(--series-gbm)]/50")}>
      <CardHeader>
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <Badge variant="outline">{m.tour.toUpperCase()}</Badge>
          <span className="truncate">{m.tournament}</span>
          <span className="ml-auto inline-flex items-center gap-1 whitespace-nowrap">
            <Clock className="size-3.5" /> {localTime(m.commence_time)} · {startsIn(m.commence_time)}
          </span>
        </div>
        <CardTitle className="mt-2 flex items-baseline justify-between gap-3 text-base">
          <span className={cn("truncate", m.pick && pickIs1 && "underline decoration-[var(--series-gbm)] decoration-2 underline-offset-4")}>{m.player_1}</span>
          <span className="text-xs font-normal text-muted-foreground">vs</span>
          <span className={cn("truncate text-right", m.pick && !pickIs1 && "underline decoration-[var(--series-gbm)] decoration-2 underline-offset-4")}>{m.player_2}</span>
        </CardTitle>
      </CardHeader>
      <CardContent className="grid gap-2">
        <ProbRow label="Model" p1={m.p1_model} color="var(--series-gbm)" />
        <ProbRow label="Market" p1={m.reference_p1} color="var(--series-market)" />
        <div className="mt-1 flex flex-wrap items-center gap-2 text-xs">
          {m.pick ? (
            <Badge className="bg-[var(--series-gbm)]/15 text-foreground border-[var(--series-gbm)]/40" variant="outline">
              Model leans {m.pick.split(" ").at(-1)} by {pickEdge.toFixed(1)} pts · best {pickIs1 ? m.best_odds_1.toFixed(2) : m.best_odds_2.toFixed(2)}
            </Badge>
          ) : unknown ? (
            <span className="text-muted-foreground">No pick</span>
          ) : (
            <span className="text-muted-foreground">Model agrees with the market</span>
          )}
          {move != null && Math.abs(move) >= 0.5 && (
            <Tooltip>
              <TooltipTrigger className="inline-flex items-center gap-0.5 text-muted-foreground">
                {move > 0 ? <ArrowUpRight className="size-3.5" /> : <ArrowDownRight className="size-3.5" />}
                {m.player_1.split(" ").at(-1)} {move > 0 ? "+" : ""}{move.toFixed(1)} pts since open
              </TooltipTrigger>
              <TooltipContent>Market probability for {m.player_1} moved from {pct(m.market_open_p1)} to {pct(m.reference_p1)}</TooltipContent>
            </Tooltip>
          )}
          {unknown && (
            <Tooltip>
              <TooltipTrigger className="inline-flex items-center gap-1 text-muted-foreground">
                <Info className="size-3.5" /> New player
              </TooltipTrigger>
              <TooltipContent>One player has no match history, so the model treats them as average and logs no pick.</TooltipContent>
            </Tooltip>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

function EmptyState() {
  return (
    <Card className="mt-8">
      <CardHeader>
        <CardTitle className="flex items-center gap-2"><Radio className="size-5 text-muted-foreground" /> No live odds collected yet</CardTitle>
        <CardDescription className="leading-relaxed max-w-2xl">
          The collector stores odds snapshots from The Odds API a few times a day. Once it has run, upcoming matches
          appear here with model and market probabilities.
        </CardDescription>
      </CardHeader>
      <CardContent className="text-sm grid gap-2">
        <p className="text-muted-foreground">To start it locally:</p>
        <ol className="list-decimal pl-5 grid gap-1 text-muted-foreground">
          <li>Get a free key at the-odds-api.com and add <code className="font-mono text-foreground">ODDS_API_KEY=…</code> to <code className="font-mono text-foreground">.env</code>.</li>
          <li>Run <code className="font-mono text-foreground">powershell scripts/collect_odds.ps1</code>, or schedule it.</li>
        </ol>
      </CardContent>
    </Card>
  );
}

function TrackerPanel({ t }: { t: Tracker }) {
  return (
    <section className="mt-16">
      <h2 className="text-2xl font-semibold tracking-tight">Pick tracker</h2>
      <p className="mt-2 max-w-3xl text-muted-foreground leading-relaxed">
        Each logged pick is graded by closing line value: did the market move toward it before the match started? Over
        a few hundred picks, consistently beating the close is the clearest sign of a real edge.
      </p>
      <div className="mt-6 grid gap-4 sm:grid-cols-3">
        {[
          { v: String(t.graded), l: "picks graded" },
          { v: t.beat_close == null ? "—" : pct(t.beat_close, 0), l: "beat the closing line" },
          { v: t.avg_clv == null ? "—" : `${t.avg_clv > 0 ? "+" : ""}${t.avg_clv.toFixed(2)} pts`, l: "average price move toward pick" },
        ].map((s) => (
          <Card key={s.l} size="sm"><CardContent><div className="text-3xl font-semibold tracking-tight">{s.v}</div><div className="text-sm text-muted-foreground mt-1">{s.l}</div></CardContent></Card>
        ))}
      </div>
      {t.picks.length > 0 ? (
        <Card className="mt-6">
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Match</TableHead>
                  <TableHead>Pick</TableHead>
                  <TableHead className="text-right">At pick</TableHead>
                  <TableHead className="text-right">At close</TableHead>
                  <TableHead className="text-right">Result</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {t.picks.map((p) => (
                  <TableRow key={p.event_id}>
                    <TableCell className="whitespace-normal"><div>{p.player_1} vs {p.player_2}</div><div className="text-xs text-muted-foreground">{p.tournament}</div></TableCell>
                    <TableCell>{p.pick}</TableCell>
                    <TableCell className="text-right font-mono tabular-nums">{pct(p.pick_ref_prob)}</TableCell>
                    <TableCell className="text-right font-mono tabular-nums">{pct(p.close_prob)}</TableCell>
                    <TableCell className="text-right">
                      <span className="inline-flex items-center gap-1">
                        {p.clv_points > 0 ? <CircleCheck className="size-4 text-[var(--good)]" /> : p.clv_points < 0 ? <CircleX className="size-4 text-[var(--critical)]" /> : <Minus className="size-4 text-muted-foreground" />}
                        {p.clv_points > 0 ? "Beat close" : p.clv_points < 0 ? "Missed" : "No move"}
                      </span>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      ) : (
        <p className="mt-6 text-sm text-muted-foreground">No graded picks yet. Picks are graded once their matches start.</p>
      )}
    </section>
  );
}

export function LiveBoard() {
  const [matches, setMatches] = useState<Upcoming[] | null>(null);
  const [tracker, setTracker] = useState<Tracker | null>(null);
  const [filter, setFilter] = useState<Filter>("all");
  const [onlyPicks, setOnlyPicks] = useState(false);

  useEffect(() => {
    const bust = `?t=${Date.now()}`;
    fetch(`/data/upcoming.json${bust}`).then((r) => r.json()).then(setMatches).catch(() => setMatches([]));
    fetch(`/data/tracker.json${bust}`).then((r) => r.json()).then(setTracker).catch(() => setTracker(null));
  }, []);

  const shown = useMemo(
    () => (matches ?? []).filter((m) => (filter === "all" || m.tour === filter) && (!onlyPicks || m.pick)),
    [matches, filter, onlyPicks],
  );

  return (
    <>
      {matches === null ? (
        <div className="mt-8 grid gap-4 md:grid-cols-2">{[0, 1, 2, 3].map((i) => <Card key={i} className="h-40 animate-pulse" />)}</div>
      ) : matches.length === 0 ? (
        <EmptyState />
      ) : (
        <>
          <div className="mt-8 flex flex-wrap items-center gap-3">
            <Tabs value={filter} onValueChange={(v) => setFilter(v as Filter)}>
              <TabsList>
                <TabsTrigger value="all" className="px-3">All</TabsTrigger>
                <TabsTrigger value="atp" className="px-3">ATP</TabsTrigger>
                <TabsTrigger value="wta" className="px-3">WTA</TabsTrigger>
              </TabsList>
            </Tabs>
            <Button variant={onlyPicks ? "default" : "outline"} size="sm" onClick={() => setOnlyPicks(!onlyPicks)} aria-pressed={onlyPicks}>
              Only disagreements
            </Button>
            <span className="ml-auto text-sm text-muted-foreground">{shown.length} matches</span>
          </div>
          <div className="mt-4 grid gap-4 md:grid-cols-2">
            {shown.map((m) => <MatchCard key={m.event_id} m={m} />)}
          </div>
        </>
      )}
      {tracker && <TrackerPanel t={tracker} />}
    </>
  );
}
