"""Closing-line-value test: do prices move toward the model's picks?

Uses an April-October 2026 file of opening and later odds (bet365, BetMGM, Kalshi,
Polymarket) collected from Flashscore by github.com/gmalbert/tennis-predictions. For every
match, the model's pre-match probability is compared with the *opening* price. If the
model knows something the opening line doesn't, the later price should move toward the
side the model favours. Price movement is independent of who won, so it is a much less
noisy signal of skill than profit, which is why professional bettors track it.

Usage:  uv run python -m tennis_edge.eval.clv
"""

import duckdb
import numpy as np
import pandas as pd

from tennis_edge.betting.vig import proportional
from tennis_edge.clean.name_matching import full_name_keys, odds_name_key
from tennis_edge.config import DB_PATH, RAW_DIR
from tennis_edge.eval.segments import roi_ci

URL = ("https://raw.githubusercontent.com/gmalbert/tennis-predictions/main/"
       "data_files/flashscore_odds_history.csv")
PATH = RAW_DIR / "flashscore" / "odds_history.csv"
MODELS = {"LightGBM": "p_gbm_winner", "Elo": "p_elo_winner",
          "Serve/return": "p_markov_cal_winner"}


def _keys(name: str) -> list[str]:
    return [odds_name_key(name)] if "." in name else full_name_keys(name)


def load_snapshots() -> pd.DataFrame:
    if not PATH.exists():
        PATH.parent.mkdir(parents=True, exist_ok=True)
        PATH.write_bytes(pd.read_csv(URL).to_csv(index=False).encode())
    s = pd.read_csv(PATH)
    s["start"] = pd.to_datetime(s["ts_start"], unit="s")
    s["fetched"] = pd.to_datetime(s["fetched_at"]).dt.tz_localize(None)
    s["hours_before"] = (s["start"] - s["fetched"]).dt.total_seconds() / 3600
    s["tour"] = np.where(s["tourney"].str.startswith("WTA"), "wta", "atp")
    for c in ("p1_odds", "p2_odds", "p1_opening", "p2_opening"):
        s[c] = pd.to_numeric(s[c], errors="coerce")
    s = s.dropna(subset=["p1_odds", "p2_odds", "p1_opening", "p2_opening"])
    s = s[(s[["p1_odds", "p2_odds", "p1_opening", "p2_opening"]] > 1).all(axis=1)]
    # Drop placeholder prices (e.g. Polymarket opens illiquid markets at 100.0 / 1.01):
    # a real two-way price implies probabilities summing to roughly 100% plus margin.
    # 1/100 + 1/1.01 still sums to ~100%, so also cap odds and drop Polymarket, whose
    # tennis markets are too thin to have meaningful opening prices.
    s = s[~s["bookmaker_name"].str.startswith("Polymarket")]
    for a, b in (("p1_opening", "p2_opening"), ("p1_odds", "p2_odds")):
        book = 1 / s[a] + 1 / s[b]
        s = s[book.between(0.97, 1.15) & (s[[a, b]] < 30).all(axis=1)]
    return s.reset_index(drop=True)


def join_predictions(snaps: pd.DataFrame) -> pd.DataFrame:
    """Attach model probabilities that p1 wins, plus whether p1 actually won."""
    cols = ["match_date", "winner_name", "loser_name", *MODELS.values()]
    with duckdb.connect(str(DB_PATH), read_only=True) as con:
        preds = pd.concat([
            con.execute(f"SELECT '{t}' AS tour, {', '.join(cols)} FROM {t}_matches "
                        "WHERE match_date >= DATE '2026-03-01'").df()
            for t in ("atp", "wta")
        ])
    preds["wkey"] = preds["winner_name"].map(_keys)
    preds["lkey"] = preds["loser_name"].map(_keys)
    preds = preds.explode("wkey").explode("lkey")

    s = snaps.assign(k1=snaps["p1"].map(odds_name_key), k2=snaps["p2"].map(odds_name_key),
                     day=snaps["start"].dt.normalize())
    out = []
    for p1_won, (a, b) in ((True, ("wkey", "lkey")), (False, ("lkey", "wkey"))):
        m = s.merge(preds, left_on=["tour", "k1", "k2"], right_on=["tour", a, b])
        m = m[(m["match_date"] - m["day"]).dt.days.abs() <= 2]
        for col in MODELS.values():
            m[col] = m[col] if p1_won else 1 - m[col]
        out.append(m.assign(p1_won=p1_won))
    joined = pd.concat(out).drop_duplicates(["event_id", "bookmaker_id"])
    return joined.reset_index(drop=True)


def analyse(df: pd.DataFrame, min_edge: float = 0.03) -> pd.DataFrame:
    fair_open = proportional(df["p1_opening"], df["p2_opening"])
    fair_late = proportional(df["p1_odds"], df["p2_odds"])
    rows = []
    for model, col in MODELS.items():
        edge = df[col] - fair_open
        side = np.sign(edge)  # +1 = bet p1, -1 = bet p2
        move = side * (fair_late - fair_open)  # price movement toward our side
        bet = (edge.abs() > min_edge) & df[col].notna()
        open_odds = np.where(side > 0, df["p1_opening"], df["p2_opening"])
        won = np.where(side > 0, df["p1_won"], ~df["p1_won"])
        profit = np.where(won, open_odds - 1, -1.0)[bet]
        lo, hi = roi_ci(profit)
        moved = move[bet]
        rows.append({
            "model": model, "bets": int(bet.sum()),
            "moved toward us": (moved > 0).mean(), "moved against": (moved < 0).mean(),
            "avg move (prob pts)": moved.mean() * 100,
            "corr(edge, move)": np.corrcoef(df.loc[df[col].notna(), col] - fair_open[df[col].notna()],
                                            (fair_late - fair_open)[df[col].notna()])[0, 1],
            "ROI at opening odds": profit.mean(), "ROI 95% CI": f"{lo:+.1%} to {hi:+.1%}",
        })
    return pd.DataFrame(rows)


def main() -> None:
    pd.set_option("display.width", 200)
    snaps = load_snapshots()
    df = join_predictions(snaps)
    print(f"{len(snaps):,} odds snapshots; {len(df):,} matched to model predictions "
          f"({df['event_id'].nunique():,} matches)")
    print(f"Median time between opening and later price snapshot: "
          f"{df['hours_before'].median():.0f}h before start\n")
    fmt = {"moved toward us": "{:.1%}".format, "moved against": "{:.1%}".format,
           "avg move (prob pts)": "{:+.2f}".format, "corr(edge, move)": "{:+.3f}".format,
           "ROI at opening odds": "{:+.1%}".format}
    for (tour, book), g in df.groupby(["tour", "bookmaker_name"]):
        if len(g) < 100:
            continue
        print(f"== {tour.upper()} / {book}: {len(g)} matches")
        print(analyse(g).to_string(index=False, formatters=fmt), "\n")
    print("== All tours and books pooled")
    print(analyse(df).to_string(index=False, formatters=fmt))


if __name__ == "__main__":
    main()
