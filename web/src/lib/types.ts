export type ModelKey = "elo" | "serve_return" | "lightgbm";
export type Tour = "atp" | "wta";

export type ModelScore = {
  log_loss: number;
  brier: number;
  accuracy: number;
  roi: number;
  roi_ci: [number, number];
  bets: number;
};

export type Scores = {
  n_matches: number;
  n_with_odds: number;
  market: { log_loss: number; brier: number };
} & Record<ModelKey, ModelScore>;

export type TourSummary = {
  reference_book: string;
  total_matches: number;
  first_year: number;
  last_result: string;
  historical: Scores;
  unseen: Scores | null;
  unseen_range: [string, string];
};

export type Summary = { generated_at: string; tours: Record<Tour, TourSummary> };

export type EquityPoint = { date: string; bet: number; units: number };
export type Equity = Record<ModelKey, EquityPoint[]>;
export type EdgeBucket = { bucket: string; bets: number; roi: number };
export type CalibrationPoint = { predicted: number; observed: number; n: number };

export type Segment = {
  tour: Tour;
  model: string;
  book: string;
  segment: string;
  edge: string;
  disc_bets: number;
  disc_roi: number;
  val_bets: number;
  val_roi: number;
  val_ci_low: number;
  val_ci_high: number;
};
export type Segments = {
  tried: number;
  discovered: number;
  validated_positive: number;
  validated_significant: number;
  discovered_median_val_roi: number;
  top: Segment[];
};

export type ClvRow = {
  tour: Tour;
  book: string;
  matches: number;
  bets: number;
  toward: number;
  against: number;
  avg_move: number;
  corr: number;
  roi: number;
};

export type RankedPlayer = {
  id: string;
  name: string;
  elo: number;
  atp_rank: number | null;
  hard: number | null;
  clay: number | null;
  grass: number | null;
  form: number[];
  last_match: string;
  history: { month: string; elo: number }[];
};

export type Upcoming = {
  event_id: string;
  tour: Tour;
  tournament: string;
  commence_time: string;
  player_1: string;
  player_2: string;
  n_books: number;
  surface: string;
  market_p1: number;
  market_open_p1: number | null;
  sharp_p1: number | null;
  reference_p1: number;
  best_odds_1: number;
  best_odds_2: number;
  best_book_1: string;
  best_book_2: string;
  p1_model: number;
  p1_elo: number;
  p1_serve_return: number;
  edge_1: number;
  pick: string | null;
  known_1: boolean;
  known_2: boolean;
};

export type TrackedPick = {
  event_id: string;
  tour: Tour;
  tournament: string;
  commence_time: string;
  player_1: string;
  player_2: string;
  pick: string;
  pick_prob: number;
  pick_ref_prob: number;
  pick_best_odds: number;
  close_prob: number;
  clv_points: number;
  beat_close: boolean;
};

export type Tracker = {
  graded: number;
  beat_close: number | null;
  avg_clv: number | null;
  picks: TrackedPick[];
};

export const MODEL_LABEL: Record<ModelKey, string> = {
  elo: "Elo",
  serve_return: "Serve/return",
  lightgbm: "LightGBM",
};

export const MODEL_COLOR: Record<ModelKey, string> = {
  elo: "var(--series-elo)",
  serve_return: "var(--series-sr)",
  lightgbm: "var(--series-gbm)",
};
