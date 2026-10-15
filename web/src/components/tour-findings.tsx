"use client";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { CalibrationChart, EdgeBucketChart, EquityChart, GapToMarketChart, Legend, modelLegend } from "@/components/charts";
import { ci, ll, num, pct, signedPct } from "@/lib/format";
import { MODEL_COLOR, MODEL_LABEL, type CalibrationPoint, type EdgeBucket, type Equity, type ModelKey, type Tour, type TourSummary } from "@/lib/types";

export type TourData = {
  summary: TourSummary;
  equity: Equity;
  buckets: EdgeBucket[];
  calibration: CalibrationPoint[];
};

const MODELS: ModelKey[] = ["elo", "serve_return", "lightgbm"];

function ScoreTable({ data, book }: { data: TourSummary["historical"]; book: string }) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Model</TableHead>
          <TableHead className="text-right">Log loss</TableHead>
          <TableHead className="text-right hidden sm:table-cell">Accuracy</TableHead>
          <TableHead className="text-right">Betting return</TableHead>
          <TableHead className="text-right hidden xl:table-cell">95% interval</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {MODELS.map((m) => (
          <TableRow key={m}>
            <TableCell>
              <span className="inline-flex items-center gap-2">
                <span className="size-2.5 rounded-[3px]" style={{ background: MODEL_COLOR[m] }} />
                {MODEL_LABEL[m]}
              </span>
            </TableCell>
            <TableCell className="text-right font-mono tabular-nums">{ll(data[m].log_loss)}</TableCell>
            <TableCell className="text-right font-mono tabular-nums hidden sm:table-cell">{pct(data[m].accuracy)}</TableCell>
            <TableCell className="text-right font-mono tabular-nums">{signedPct(data[m].roi)}</TableCell>
            <TableCell className="text-right font-mono tabular-nums text-muted-foreground hidden xl:table-cell">
              {ci(...data[m].roi_ci)}
            </TableCell>
          </TableRow>
        ))}
        <TableRow className="bg-muted/40">
          <TableCell className="font-medium">
            <span className="inline-flex items-center gap-2">
              <span className="size-2.5 rounded-[3px]" style={{ background: "var(--series-market)" }} />
              {book} odds
            </span>
          </TableCell>
          <TableCell className="text-right font-mono tabular-nums font-medium">{ll(data.market.log_loss)}</TableCell>
          <TableCell className="text-right text-muted-foreground hidden sm:table-cell">—</TableCell>
          <TableCell className="text-right text-muted-foreground">—</TableCell>
          <TableCell className="hidden xl:table-cell" />
        </TableRow>
      </TableBody>
    </Table>
  );
}

function TourPanel({ tour, data }: { tour: Tour; data: TourData }) {
  const s = data.summary;
  const h = s.historical;
  const u = s.unseen;
  return (
    <div className="grid gap-6">
      <div className="grid gap-6 lg:grid-cols-5">
        <Card className="lg:col-span-3">
          <CardHeader>
            <CardTitle>How far behind the market?</CardTitle>
            <CardDescription>
              Extra log loss compared with {s.reference_book}&apos;s margin-free odds, 2020–2025 ({num(h.n_with_odds)} matches).
              Zero would mean as accurate as the market; every model sits above it.
            </CardDescription>
          </CardHeader>
          <CardContent className="grid gap-4">
            <GapToMarketChart scores={h} />
            <ScoreTable data={h} book={s.reference_book} />
          </CardContent>
        </Card>
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Are the probabilities honest?</CardTitle>
            <CardDescription>
              LightGBM&apos;s predicted win chance against how often those players actually won. Dots on the diagonal
              mean a 70% prediction wins about 70% of the time.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <CalibrationChart points={data.calibration} />
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>What betting on the model would have done</CardTitle>
          <CardDescription>
            Running profit from a 1-unit bet every time a model rated a player at least 3 points above the
            bookmaker&apos;s fair probability, 2020–2025. Every line ends below zero.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-3">
          <Legend items={modelLegend} />
          <EquityChart equity={data.equity} />
        </CardContent>
      </Card>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>The bigger the claimed edge, the bigger the loss</CardTitle>
            <CardDescription>
              LightGBM&apos;s return per bet grouped by how much it disagreed with the market. Big disagreements usually mean the
              market knows something the model can&apos;t see (injuries, withdrawals, motivation).
            </CardDescription>
          </CardHeader>
          <CardContent>
            <EdgeBucketChart buckets={data.buckets} />
          </CardContent>
        </Card>
        {u && (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                Unseen data check <Badge variant="outline">{num(u.n_matches)} matches</Badge>
              </CardTitle>
              <CardDescription>
                {tour.toUpperCase()} matches from {new Date(s.unseen_range[0]).toLocaleDateString("en-US", { month: "short", day: "numeric" })} to{" "}
                {new Date(s.unseen_range[1]).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })}, which no model or
                analysis touched while being built, scored against one bookmaker&apos;s odds.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <ScoreTable data={u} book="Bookmaker" />
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}

export function TourFindings({ atp, wta }: { atp: TourData; wta: TourData }) {
  return (
    <Tabs defaultValue="atp" className="gap-6">
      <TabsList>
        <TabsTrigger value="atp" className="px-4">ATP (men)</TabsTrigger>
        <TabsTrigger value="wta" className="px-4">WTA (women)</TabsTrigger>
      </TabsList>
      <TabsContent value="atp">
        <TourPanel tour="atp" data={atp} />
      </TabsContent>
      <TabsContent value="wta">
        <TourPanel tour="wta" data={wta} />
      </TabsContent>
    </Tabs>
  );
}
