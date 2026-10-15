export const pct = (x: number | null | undefined, digits = 1) =>
  x == null ? "—" : `${(x * 100).toFixed(digits)}%`;

export const signedPct = (x: number | null | undefined, digits = 1) =>
  x == null ? "—" : `${x > 0 ? "+" : x < 0 ? "−" : ""}${Math.abs(x * 100).toFixed(digits)}%`;

export const num = (x: number | null | undefined, digits = 0) =>
  x == null ? "—" : x.toLocaleString("en-US", { maximumFractionDigits: digits, minimumFractionDigits: digits });

export const ll = (x: number) => x.toFixed(3);

export const ci = (lo: number, hi: number) => `${signedPct(lo)} to ${signedPct(hi)}`;

export const date = (iso: string) =>
  new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
