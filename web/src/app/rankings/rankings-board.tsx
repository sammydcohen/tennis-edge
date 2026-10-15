"use client";

import { useMemo, useState, useSyncExternalStore } from "react";
import { Search } from "lucide-react";
import { cn } from "cn";

import { Sparkline } from "@/components/charts";
import { Card, CardContent } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type { RankedPlayer, Tour } from "@/lib/types";

const WIDE = "(min-width: 1024px)";
function subscribeWide(onChange: () => void) {
  const mq = matchMedia(WIDE);
  mq.addEventListener("change", onChange);
  return () => mq.removeEventListener("change", onChange);
}

type Surface = "elo" | "hard" | "clay" | "grass";
const SURFACES: { key: Surface; label: string }[] = [
  { key: "elo", label: "Overall" },
  { key: "hard", label: "Hard" },
  { key: "clay", label: "Clay" },
  { key: "grass", label: "Grass" },
];

function Form({ results }: { results: number[] }) {
  return (
    <div className="flex gap-1" aria-label={`Last ${results.length}: ${results.filter(Boolean).length} wins`}>
      {results.map((w, i) => (
        <span
          key={i}
          title={w ? "Win" : "Loss"}
          className={cn(
            "grid size-4 place-items-center rounded-[4px] text-[9px] font-semibold",
            w ? "bg-[var(--pos)]/20 text-foreground" : "bg-muted text-muted-foreground",
          )}
        >
          {w ? "W" : "L"}
        </span>
      ))}
    </div>
  );
}

export function RankingsBoard({ atp, wta }: { atp: RankedPlayer[]; wta: RankedPlayer[] }) {
  const [tour, setTour] = useState<Tour>("atp");
  const [surface, setSurface] = useState<Surface>("elo");
  const [query, setQuery] = useState("");
  // Sparklines only show on wide screens; skip rendering them (and Recharts' 0-width warnings) otherwise.
  const wide = useSyncExternalStore(subscribeWide, () => matchMedia(WIDE).matches, () => false);

  const rows = useMemo(() => {
    const list = (tour === "atp" ? atp : wta).filter((p) => p[surface] != null);
    return [...list]
      .sort((a, b) => (b[surface] as number) - (a[surface] as number))
      .map((p, i) => ({ ...p, pos: i + 1 }))
      .filter((p) => p.name.toLowerCase().includes(query.toLowerCase()));
  }, [tour, surface, query, atp, wta]);

  return (
    <>
      <div className="mt-8 flex flex-wrap items-center gap-3">
        <Tabs value={tour} onValueChange={(v) => setTour(v as Tour)}>
          <TabsList>
            <TabsTrigger value="atp" className="px-3">ATP</TabsTrigger>
            <TabsTrigger value="wta" className="px-3">WTA</TabsTrigger>
          </TabsList>
        </Tabs>
        <Tabs value={surface} onValueChange={(v) => setSurface(v as Surface)}>
          <TabsList>
            {SURFACES.map((s) => (
              <TabsTrigger key={s.key} value={s.key} className="px-3">{s.label}</TabsTrigger>
            ))}
          </TabsList>
        </Tabs>
        <label className="relative ml-auto w-full sm:w-64">
          <span className="sr-only">Search players</span>
          <Search className="absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search players"
            className="h-8 w-full rounded-lg border bg-transparent pl-8 pr-3 text-sm outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50"
          />
        </label>
      </div>
      <Card className="mt-4">
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-10">#</TableHead>
                <TableHead>Player</TableHead>
                <TableHead className="text-right">{SURFACES.find((s) => s.key === surface)!.label} Elo</TableHead>
                <TableHead className="text-right hidden sm:table-cell">{tour.toUpperCase()} rank</TableHead>
                <TableHead className="hidden md:table-cell">Last 10</TableHead>
                <TableHead className="hidden lg:table-cell">3-year trend</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((p) => (
                <TableRow key={p.id}>
                  <TableCell className="font-mono tabular-nums text-muted-foreground">{p.pos}</TableCell>
                  <TableCell className="font-medium">{p.name}</TableCell>
                  <TableCell className="text-right font-mono tabular-nums">{Math.round(p[surface] as number)}</TableCell>
                  <TableCell className="text-right font-mono tabular-nums text-muted-foreground hidden sm:table-cell">{p.atp_rank ?? "—"}</TableCell>
                  <TableCell className="hidden md:table-cell"><Form results={p.form} /></TableCell>
                  <TableCell className="hidden lg:table-cell py-1">{wide && <Sparkline values={p.history.map((h) => h.elo)} />}</TableCell>
                </TableRow>
              ))}
              {rows.length === 0 && (
                <TableRow><TableCell colSpan={6} className="text-center text-muted-foreground py-8">No players match “{query}”.</TableCell></TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </>
  );
}
