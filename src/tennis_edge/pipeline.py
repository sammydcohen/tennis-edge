"""End-to-end: download -> join odds -> Elo -> DuckDB -> baseline evaluation.

Usage:  uv run python -m tennis_edge.pipeline --tour atp --start 2005 --end 2025
"""

import argparse

import duckdb
import pandas as pd

from tennis_edge.betting import backtest
from tennis_edge.betting.vig import proportional
from tennis_edge.clean.name_matching import attach_odds
from tennis_edge.config import DB_PATH
from tennis_edge.eval.metrics import accuracy, brier, log_loss, symmetric
from tennis_edge.features.elo import compute_elo
from tennis_edge.ingest import odds_history, sackmann

ODDS_COLS = ["psw", "psl", "b365w", "b365l", "maxw", "maxl", "avgw", "avgl"]


def build(tour: str, start: int, end: int, elo_burn_in: int = 1990) -> pd.DataFrame:
    # Elo needs history before the evaluation window to settle.
    matches = sackmann.load(tour, range(min(elo_burn_in, start), end + 1))
    matches = compute_elo(matches)
    matches = matches[matches["tourney_date"].dt.year >= start]
    odds = odds_history.load(tour, range(max(start, 2001), end + 1))
    if odds.empty:
        print("No odds files available - see ingest/odds_history.py for manual download.")
        joined = matches.assign(odds_matched=False, match_date=pd.NaT,
                                **{c: float("nan") for c in ODDS_COLS})
    else:
        joined = attach_odds(matches, odds)
    joined["match_date"] = joined["match_date"].fillna(joined["tourney_date"])

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(str(DB_PATH)) as con:
        con.execute(f"CREATE OR REPLACE TABLE {tour}_matches AS SELECT * FROM joined")
    return joined


def evaluate(df: pd.DataFrame) -> None:
    rated = df.dropna(subset=["p_elo_winner"])
    p, y = symmetric(rated["p_elo_winner"])
    print(f"\nElo baseline on {len(rated):,} matches")
    print(f"  log loss {log_loss(p, y):.4f}  brier {brier(p, y):.4f}  acc {accuracy(p, y):.3f}")

    for year, g in rated.groupby(rated["tourney_date"].dt.year):
        py, yy = symmetric(g["p_elo_winner"])
        print(f"  {year}: log loss {log_loss(py, yy):.4f}  acc {accuracy(py, yy):.3f}  n={len(g)}")

    with_odds = rated.dropna(subset=["psw", "psl"])
    if with_odds.empty:
        print("\nNo odds joined - skipping market comparison and backtest.")
        return
    with_odds = with_odds[(with_odds["psw"] > 1) & (with_odds["psl"] > 1)]
    print(f"\nOdds matched for {df['odds_matched'].mean():.1%} of matches; "
          f"{len(with_odds):,} have Pinnacle odds")
    pe, ye = symmetric(with_odds["p_elo_winner"])
    pm, ym = symmetric(proportional(with_odds["psw"], with_odds["psl"]))
    print(f"  Elo    log loss {log_loss(pe, ye):.4f}  brier {brier(pe, ye):.4f}")
    print(f"  Market log loss {log_loss(pm, ym):.4f}  brier {brier(pm, ym):.4f}")

    for book, (w, l) in {"Pinnacle": ("psw", "psl"), "Bet365": ("b365w", "b365l"),
                         "Market max": ("maxw", "maxl")}.items():
        res = backtest.run(rated.assign(p_model=rated["p_elo_winner"]), w, l)
        print(f"  Backtest vs {book:<10} {res.summary()}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tour", default="atp", choices=["atp", "wta"])
    ap.add_argument("--start", type=int, default=2010)
    ap.add_argument("--end", type=int, default=2025)
    args = ap.parse_args()
    evaluate(build(args.tour, args.start, args.end))


if __name__ == "__main__":
    main()
