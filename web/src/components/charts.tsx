"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  LabelList,
  Line,
  LineChart,
  ReferenceLine,
  Scatter,
  ScatterChart,
  XAxis,
  YAxis,
  ZAxis,
} from "recharts";

import { ChartContainer, ChartTooltip, type ChartConfig } from "@/components/ui/chart";
import { signedPct, pct, num } from "@/lib/format";
import {
  MODEL_COLOR,
  MODEL_LABEL,
  type CalibrationPoint,
  type EdgeBucket,
  type Equity,
  type ModelKey,
  type Scores,
} from "@/lib/types";

const MODELS: ModelKey[] = ["elo", "serve_return", "lightgbm"];
const AXIS = { tickLine: false, axisLine: false, fontSize: 12 } as const;

function TooltipBox({ title, rows }: { title?: string; rows: { label: string; value: string; color?: string }[] }) {
  return (
    <div className="rounded-lg border bg-popover px-3 py-2 text-xs shadow-md min-w-40">
      {title && <div className="mb-1.5 font-medium text-foreground">{title}</div>}
      <div className="grid gap-1">
        {rows.map((r) => (
          <div key={r.label} className="flex items-center gap-2">
            {r.color && <span className="size-2.5 rounded-[3px]" style={{ background: r.color }} />}
            <span className="text-muted-foreground">{r.label}</span>
            <span className="ml-auto font-mono tabular-nums text-foreground">{r.value}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export function Legend({ items }: { items: { label: string; color: string }[] }) {
  return (
    <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
      {items.map((i) => (
        <span key={i.label} className="inline-flex items-center gap-1.5">
          <span className="size-2.5 rounded-[3px]" style={{ background: i.color }} />
          {i.label}
        </span>
      ))}
    </div>
  );
}

export const modelLegend = MODELS.map((m) => ({ label: MODEL_LABEL[m], color: MODEL_COLOR[m] }));

/** How far each model's log loss sits above the market's (0 = as good as the market). */
export function GapToMarketChart({ scores }: { scores: Scores }) {
  const data = MODELS.map((m) => ({
    model: MODEL_LABEL[m],
    key: m,
    gap: (scores[m].log_loss - scores.market.log_loss) * 1000,
    logLoss: scores[m].log_loss,
  }));
  const config: ChartConfig = { gap: { label: "Gap to market" } };
  return (
    <ChartContainer config={config} className="aspect-auto h-[190px] w-full">
      <BarChart data={data} layout="vertical" margin={{ left: 8, right: 56, top: 4, bottom: 4 }} barCategoryGap={14}>
        <CartesianGrid horizontal={false} strokeOpacity={0.5} />
        <XAxis type="number" {...AXIS} domain={[0, (max: number) => Math.ceil(max / 10) * 10]} allowDecimals={false} tickFormatter={(v) => `+${v}`} />
        <YAxis type="category" dataKey="model" {...AXIS} width={92} />
        <ChartTooltip
          cursor={{ fillOpacity: 0.4 }}
          content={({ active, payload }) =>
            active && payload?.[0] ? (
              <TooltipBox
                title={payload[0].payload.model}
                rows={[
                  { label: "Model log loss", value: payload[0].payload.logLoss.toFixed(4) },
                  { label: "Market log loss", value: scores.market.log_loss.toFixed(4) },
                  { label: "Gap (×1000)", value: `+${payload[0].payload.gap.toFixed(1)}` },
                ]}
              />
            ) : null
          }
        />
        <Bar dataKey="gap" radius={[0, 4, 4, 0]} maxBarSize={22} isAnimationActive={false}>
          {data.map((d) => (
            <Cell key={d.key} fill={MODEL_COLOR[d.key]} />
          ))}
          <LabelList dataKey="gap" position="right" className="fill-foreground" fontSize={12} formatter={(v) => `+${Number(v).toFixed(1)}`} />
        </Bar>
      </BarChart>
    </ChartContainer>
  );
}

/** Cumulative profit (units, flat 1-unit stakes) for each model's value bets. */
export function EquityChart({ equity }: { equity: Equity }) {
  // Merge the three curves onto a common bet-number axis.
  const byBet = new Map<number, Record<string, number | string>>();
  for (const m of MODELS)
    for (const p of equity[m]) {
      const row = byBet.get(p.bet) ?? { bet: p.bet };
      row[m] = p.units;
      row[`${m}_date`] = p.date;
      byBet.set(p.bet, row);
    }
  const data = [...byBet.values()].sort((a, b) => Number(a.bet) - Number(b.bet));
  const config: ChartConfig = Object.fromEntries(MODELS.map((m) => [m, { label: MODEL_LABEL[m], color: MODEL_COLOR[m] }]));
  const finals = Object.fromEntries(MODELS.map((m) => [m, equity[m].at(-1)?.units ?? 0])) as Record<ModelKey, number>;
  const maxBet = Number(data.at(-1)?.bet ?? 0);
  const step = maxBet > 6000 ? 2000 : maxBet > 2500 ? 1000 : 250;
  const xTicks = Array.from({ length: Math.floor(maxBet / step) + 1 }, (_, i) => i * step);
  const lastIndex = Object.fromEntries(
    MODELS.map((m) => [m, data.findLastIndex((r) => r[m] != null)]),
  ) as Record<ModelKey, number>;

  return (
    <ChartContainer config={config} className="aspect-auto h-[300px] w-full">
      <LineChart data={data} margin={{ left: 4, right: 128, top: 8, bottom: 16 }}>
        <CartesianGrid vertical={false} strokeOpacity={0.5} />
        <XAxis dataKey="bet" type="number" domain={[0, "dataMax"]} ticks={xTicks} {...AXIS} tickFormatter={(v) => num(v)}
          label={{ value: "Bets placed", position: "insideBottom", offset: -10, fontSize: 12, className: "fill-muted-foreground" }} />
        <YAxis {...AXIS} width={48} tickFormatter={(v) => `${v > 0 ? "+" : ""}${v}`} />
        <ReferenceLine y={0} stroke="var(--muted-foreground)" strokeOpacity={0.6} />
        <ChartTooltip
          cursor={{ stroke: "var(--border)" }}
          content={({ active, payload, label }) =>
            active && payload?.length ? (
              <TooltipBox
                title={`After ${num(Number(label))} bets`}
                rows={MODELS.filter((m) => payload.some((p) => p.dataKey === m)).map((m) => {
                  const v = Number(payload.find((p) => p.dataKey === m)?.value);
                  return { label: MODEL_LABEL[m], value: `${v > 0 ? "+" : ""}${v.toFixed(0)} units`, color: MODEL_COLOR[m] };
                })}
              />
            ) : null
          }
        />
        {MODELS.map((m) => (
          <Line key={m} dataKey={m} type="monotone" stroke={MODEL_COLOR[m]} strokeWidth={2} dot={false} connectNulls isAnimationActive={false}>
            <LabelList
              dataKey={m}
              content={({ x, y, index }) =>
                index === lastIndex[m] ? (
                  <text x={Number(x) + 8} y={Number(y)} dy={4} fontSize={12} className="fill-foreground">
                    {MODEL_LABEL[m]} {finals[m] > 0 ? "+" : ""}
                    {finals[m].toFixed(0)}
                  </text>
                ) : null
              }
            />
          </Line>
        ))}
      </LineChart>
    </ChartContainer>
  );
}

/** ROI by how large an edge the model claimed. Positive/negative is polarity: blue/red. */
export function EdgeBucketChart({ buckets }: { buckets: EdgeBucket[] }) {
  const config: ChartConfig = { roi: { label: "ROI" } };
  const data = buckets.map((b) => ({ ...b, roiPct: b.roi * 100 }));
  return (
    <ChartContainer config={config} className="aspect-auto h-[240px] w-full">
      <BarChart data={data} margin={{ left: 4, right: 8, top: 24, bottom: 4 }} barCategoryGap="28%">
        <CartesianGrid vertical={false} strokeOpacity={0.5} />
        <XAxis dataKey="bucket" {...AXIS} tickFormatter={(v) => `${v} edge`} />
        <YAxis {...AXIS} width={44} tickFormatter={(v) => `${v}%`} />
        <ReferenceLine y={0} stroke="var(--muted-foreground)" strokeOpacity={0.6} />
        <ChartTooltip
          cursor={{ fillOpacity: 0.4 }}
          content={({ active, payload }) =>
            active && payload?.[0] ? (
              <TooltipBox
                title={`Claimed edge ${payload[0].payload.bucket}`}
                rows={[
                  { label: "Bets", value: num(payload[0].payload.bets) },
                  { label: "Return per bet", value: signedPct(payload[0].payload.roi) },
                ]}
              />
            ) : null
          }
        />
        <Bar dataKey="roiPct" radius={4} maxBarSize={48} isAnimationActive={false}>
          {data.map((d) => (
            <Cell key={d.bucket} fill={d.roi >= 0 ? "var(--pos)" : "var(--neg)"} />
          ))}
          <LabelList dataKey="roi" position="top" fontSize={12} className="fill-foreground" formatter={(v) => signedPct(Number(v))} />
        </Bar>
      </BarChart>
    </ChartContainer>
  );
}

/** Predicted vs observed win rate; dots on the diagonal mean honest probabilities. */
export function CalibrationChart({ points }: { points: CalibrationPoint[] }) {
  const config: ChartConfig = { observed: { label: "Observed", color: "var(--series-gbm)" } };
  const data = points.map((p) => ({ x: p.predicted * 100, y: p.observed * 100, n: p.n }));
  return (
    <ChartContainer config={config} className="aspect-square max-h-[300px] w-full">
      <ScatterChart margin={{ left: 4, right: 12, top: 8, bottom: 16 }}>
        <CartesianGrid strokeOpacity={0.5} />
        <XAxis dataKey="x" type="number" domain={[0, 100]} ticks={[0, 25, 50, 75, 100]} {...AXIS} tickFormatter={(v) => `${v}%`}
          label={{ value: "Predicted win chance", position: "insideBottom", offset: -10, fontSize: 12, className: "fill-muted-foreground" }} />
        <YAxis dataKey="y" type="number" domain={[0, 100]} ticks={[0, 25, 50, 75, 100]} {...AXIS} width={56} tickFormatter={(v) => `${v}%`}
          label={{ value: "Actually won", angle: -90, position: "insideLeft", offset: 0, fontSize: 12, className: "fill-muted-foreground", style: { textAnchor: "middle" } }} />
        <ZAxis dataKey="n" range={[80, 80]} />
        <ReferenceLine segment={[{ x: 0, y: 0 }, { x: 100, y: 100 }]} stroke="var(--muted-foreground)" strokeOpacity={0.6} />
        <ChartTooltip
          content={({ active, payload }) =>
            active && payload?.[0] ? (
              <TooltipBox
                rows={[
                  { label: "Predicted", value: pct(payload[0].payload.x / 100) },
                  { label: "Actually won", value: pct(payload[0].payload.y / 100) },
                  { label: "Matches", value: num(payload[0].payload.n) },
                ]}
              />
            ) : null
          }
        />
        <Scatter data={data} fill="var(--series-gbm)" stroke="var(--card)" strokeWidth={2} isAnimationActive={false} />
      </ScatterChart>
    </ChartContainer>
  );
}

export function Sparkline({ values }: { values: number[] }) {
  const data = values.map((v, i) => ({ i, v }));
  return (
    <ChartContainer config={{ v: { label: "Elo" } }} className="aspect-auto h-8 w-28">
      <LineChart data={data} margin={{ top: 2, bottom: 2, left: 2, right: 2 }}>
        <YAxis hide domain={["dataMin - 10", "dataMax + 10"]} />
        <Line dataKey="v" stroke="var(--series-elo)" strokeWidth={1.5} dot={false} isAnimationActive={false} />
      </LineChart>
    </ChartContainer>
  );
}
