import Link from "next/link";
import { ArrowDown, Database, FlaskConical, LineChart, Scale, Sigma } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { TourFindings, type TourData } from "@/components/tour-findings";
import { getCalibration, getClv, getEdgeBuckets, getEquity, getSegments, getSummary } from "@/lib/data";
import { num, pct, signedPct } from "@/lib/format";
import type { Tour } from "@/lib/types";

function Section({ id, eyebrow, title, intro, children }: {
  id: string; eyebrow: string; title: string; intro: React.ReactNode; children: React.ReactNode;
}) {
  return (
    <section id={id} className="mx-auto max-w-6xl px-4 sm:px-6 pt-20 scroll-mt-16">
      <p className="text-sm font-medium text-muted-foreground">{eyebrow}</p>
      <h2 className="mt-1 text-2xl sm:text-3xl font-semibold tracking-tight">{title}</h2>
      <div className="mt-3 max-w-3xl text-muted-foreground leading-relaxed">{intro}</div>
      <div className="mt-8">{children}</div>
    </section>
  );
}

function Stat({ value, label, note }: { value: string; label: string; note: string }) {
  return (
    <Card size="sm" className="gap-1">
      <CardContent>
        <div className="text-3xl font-semibold tracking-tight">{value}</div>
        <div className="mt-1 text-sm font-medium">{label}</div>
        <div className="mt-1 text-xs text-muted-foreground leading-relaxed">{note}</div>
      </CardContent>
    </Card>
  );
}

const STEPS = [
  { icon: Database, title: "Data", text: "150k+ ATP and WTA matches since 2000 (Sackmann), joined to bookmaker odds by fuzzy name and date matching, kept current with daily result feeds. Stored in DuckDB." },
  { icon: Sigma, title: "Elo ratings", text: "Overall and surface-specific ratings with experience-decayed K-factor and layoff decay, tuned on 2010–19 and scored on 2020–25." },
  { icon: FlaskConical, title: "Serve/return model", text: "Opponent-adjusted serve and return strengths feed a point → game → tiebreak → set → match Markov chain, then calibrated." },
  { icon: LineChart, title: "LightGBM", text: "Combines both models with ranking, age, form, fatigue and head-to-head features. Trained walk-forward: each year predicted only from earlier years." },
  { icon: Scale, title: "Market tests", text: "Margin removal, backtests with bootstrap confidence intervals, a discovery/validation niche search, and closing-line-value tests." },
];

export default function Home() {
  const summary = getSummary();
  const tourData = (tour: Tour): TourData => ({
    summary: summary.tours[tour],
    equity: getEquity(tour),
    buckets: getEdgeBuckets(tour),
    calibration: getCalibration(tour),
  });
  const segments = getSegments();
  const clv = getClv();
  const atp = summary.tours.atp.historical;
  const gapClosed = (atp.elo.log_loss - atp.lightgbm.log_loss) / (atp.elo.log_loss - atp.market.log_loss);
  const totalMatches = summary.tours.atp.total_matches + summary.tours.wta.total_matches;

  return (
    <>
      <section className="border-b bg-gradient-to-b from-muted/50 to-background">
        <div className="mx-auto max-w-6xl px-4 sm:px-6 pt-16 pb-14">
          <Badge variant="outline" className="mb-5">A sports-analytics research project</Badge>
          <h1 className="max-w-3xl text-4xl sm:text-5xl font-semibold tracking-tight leading-[1.1]">
            Can a model beat the tennis betting market?
          </h1>
          <p className="mt-5 max-w-2xl text-lg text-muted-foreground leading-relaxed">
            I built three match-prediction models of increasing sophistication and tested them against bookmaker
            odds as strictly as I could. The short answer: <span className="text-foreground font-medium">not on public data</span>.
            The longer answer covers how close they got, and why the market still wins.
          </p>
          <a href="#findings" className="mt-8 inline-flex items-center gap-2 text-sm font-medium hover:underline underline-offset-4">
            See the findings <ArrowDown className="size-4" />
          </a>

          <div className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Stat value={num(totalMatches)} label="matches modelled" note="ATP and WTA, 2000 to today, with pre-match features only" />
            <Stat value={pct(atp.lightgbm.accuracy, 0)} label="best model accuracy" note={`LightGBM picks the ATP winner; log loss ${atp.lightgbm.log_loss.toFixed(3)} vs Pinnacle's ${atp.market.log_loss.toFixed(3)}`} />
            <Stat value={pct(gapClosed, 0)} label="of the gap to the market closed" note="LightGBM over plain Elo, measured against Pinnacle's closing odds" />
            <Stat value={`0 / ${num(segments.tried)}`} label="niches with a proven edge" note="Betting niches that stayed profitable with confidence on years the search never saw" />
          </div>
        </div>
      </section>

      <Section
        id="findings"
        eyebrow="1 · Model vs market"
        title="Better models, still behind the bookmakers"
        intro={<>Every number here is out-of-sample: each year from 2020 on is predicted by models trained only on earlier years. Lower log loss means better probabilities.</>}
      >
        <TourFindings atp={tourData("atp")} wta={tourData("wta")} />
      </Section>

      <Section
        id="niches"
        eyebrow="2 · Searching for a niche"
        title="Looking for an edge without fooling myself"
        intro={<>An edge might exist in only part of the market, but test enough slices and some will look profitable by luck. So the search was split in time: slices were picked on 2020–22, then re-tested on 2023–25, which the search never saw.</>}
      >
        <div className="grid gap-6 lg:grid-cols-5">
          <Card className="lg:col-span-2">
            <CardHeader>
              <CardTitle>The funnel</CardTitle>
              <CardDescription>Model × bookmaker × condition × edge size, ATP and WTA.</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-3">
              {[
                { n: segments.tried, label: "slices tested" },
                { n: segments.discovered, label: "profitable in 2020–22 (≥150 bets)" },
                { n: segments.validated_positive, label: "still profitable in 2023–25" },
                { n: segments.validated_significant, label: "profitable with 95% confidence" },
              ].map((step) => (
                <div key={step.label} className="grid gap-1">
                  <div className="flex items-baseline justify-between text-sm">
                    <span>{step.label}</span>
                    <span className="font-mono font-medium">{num(step.n)}</span>
                  </div>
                  <div className="h-2 rounded-full bg-muted overflow-hidden">
                    <div className="h-full rounded-full bg-[var(--series-elo)]" style={{ width: `${Math.max(1, (step.n / segments.tried) * 100)}%` }} />
                  </div>
                </div>
              ))}
              <p className="mt-2 text-sm text-muted-foreground leading-relaxed">
                The &quot;winners&quot; from the first period averaged {signedPct(segments.discovered_median_val_roi)} per bet afterwards,
                the same as betting on everything. That&apos;s what lucky streaks look like.
              </p>
            </CardContent>
          </Card>
          <Card className="lg:col-span-3">
            <CardHeader>
              <CardTitle>Best-looking survivors</CardTitle>
              <CardDescription>The top slices by return in the validation years. None clears zero with confidence.</CardDescription>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Slice</TableHead>
                    <TableHead className="text-right">2020–22</TableHead>
                    <TableHead className="text-right">2023–25</TableHead>
                    <TableHead className="text-right hidden md:table-cell">95% interval</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {segments.top.slice(0, 6).map((s, i) => (
                    <TableRow key={i}>
                      <TableCell className="whitespace-normal">
                        <div className="font-medium">{s.tour.toUpperCase()} · {s.model} · {s.edge}</div>
                        <div className="text-xs text-muted-foreground">{s.segment}, vs {s.book}</div>
                      </TableCell>
                      <TableCell className="text-right font-mono tabular-nums">{signedPct(s.disc_roi)}</TableCell>
                      <TableCell className="text-right font-mono tabular-nums">{signedPct(s.val_roi)}</TableCell>
                      <TableCell className="text-right font-mono tabular-nums text-muted-foreground hidden md:table-cell">
                        {signedPct(s.val_ci_low)} to {signedPct(s.val_ci_high)}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </div>
      </Section>

      <Section
        id="clv"
        eyebrow="3 · Closing line value"
        title="Do prices move toward the model?"
        intro={<>Profit is noisy. Professionals judge a model by whether the odds later move in its direction. This uses opening and later prices for {num(clv.reduce((a, r) => a + r.matches, 0))} matches from April–October 2026.</>}
      >
        <Card>
          <CardContent className="pt-2">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Market</TableHead>
                  <TableHead>Price moved toward the model&apos;s pick vs against</TableHead>
                  <TableHead className="text-right">Avg move</TableHead>
                  <TableHead className="text-right">Return at opening odds</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {clv.map((r) => (
                  <TableRow key={`${r.tour}-${r.book}`}>
                    <TableCell className="font-medium">{r.tour.toUpperCase()} · {r.book.replace(".us", "")}</TableCell>
                    <TableCell className="min-w-56">
                      <div className="flex items-center gap-3">
                        <div className="flex h-2 w-40 overflow-hidden rounded-full bg-muted">
                          <div className="h-full bg-[var(--pos)]" style={{ width: `${r.toward * 100}%` }} />
                          <div className="h-full" style={{ width: `${(1 - r.toward - r.against) * 100}%` }} />
                          <div className="h-full bg-[var(--neg)]" style={{ width: `${r.against * 100}%` }} />
                        </div>
                        <span className="font-mono text-xs tabular-nums text-muted-foreground">
                          {pct(r.toward, 0)} toward · {pct(r.against, 0)} against
                        </span>
                      </div>
                    </TableCell>
                    <TableCell className="text-right font-mono tabular-nums">{r.avg_move > 0 ? "+" : ""}{r.avg_move.toFixed(1)} pts</TableCell>
                    <TableCell className="text-right font-mono tabular-nums">{signedPct(r.roi)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            <p className="mt-4 text-sm text-muted-foreground leading-relaxed max-w-3xl">
              Prices do drift toward the model more often than away, most clearly on Kalshi&apos;s ATP markets. So the model knows
              a little that opening prices don&apos;t. But the drift is about one probability point, while bookmakers charge
              around five, so it can&apos;t be turned into profit. Tracking this live against Pinnacle is the next test, on the{" "}
              <Link href="/live/" className="text-foreground underline underline-offset-4">Live matches</Link> page.
            </p>
          </CardContent>
        </Card>
      </Section>

      <Section id="method" eyebrow="4 · How it works" title="The pipeline" intro="Python end to end, with tests; this site is a static Next.js export of its results.">
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
          {STEPS.map((s, i) => (
            <Card key={s.title} size="sm">
              <CardHeader>
                <s.icon className="size-5 text-muted-foreground" />
                <CardTitle className="mt-2">{i + 1}. {s.title}</CardTitle>
              </CardHeader>
              <CardContent className="text-sm text-muted-foreground leading-relaxed">{s.text}</CardContent>
            </Card>
          ))}
        </div>
      </Section>

      <Section id="conclusion" eyebrow="5 · Conclusion" title="What I learned" intro={null}>
        <div className="grid gap-4 md:grid-cols-3">
          {[
            ["The market is efficient on public data", "Every model trailed the bookmakers' probabilities, and no betting strategy survived testing on unseen years. That includes ones that looked great at first."],
            ["How you test matters more than the model", "Walk-forward training, a held-out validation period, a pre-stated hypothesis tested on fresh 2026 data, and confidence intervals all killed results that naive backtests called profitable."],
            ["Where an edge could live", "Markets with less attention (Challengers, early lines) and information that moves fast. Those need data that isn't free, which is where the live odds collector comes in."],
          ].map(([t, d]) => (
            <Card key={t}>
              <CardHeader>
                <CardTitle>{t}</CardTitle>
                <CardDescription className="leading-relaxed">{d}</CardDescription>
              </CardHeader>
            </Card>
          ))}
        </div>
      </Section>
    </>
  );
}
