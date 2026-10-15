"""End-to-end: download -> features -> join odds -> DuckDB -> walk-forward models -> evaluation.

Usage:  uv run python -m tennis_edge.pipeline --tour atp --start 2000 --test-from 2020 --end 2025
"""

import argparse

import duckdb
import numpy as np
import pandas as pd

from tennis_edge.betting import backtest
from tennis_edge.betting.vig import proportional
from tennis_edge.clean.name_matching import attach_odds
from tennis_edge.config import DB_PATH
from tennis_edge.eval.metrics import accuracy, brier, log_loss, symmetric
from tennis_edge.features.elo import EloParams, compute_elo
from tennis_edge.features.form import compute_form
from tennis_edge.features.serve_return import compute_serve_return
from tennis_edge.ingest import odds_history, odds_kaggle, sackmann
from tennis_edge.models.gbm import walk_forward
from tennis_edge.models.tune_elo import PARAMS_PATH

ODDS_COLS = ["psw", "psl", "b365w", "b365l", "maxw", "maxl", "avgw", "avgl", "oddw", "oddl"]
MODELS = {"Elo": "p_elo_winner", "Serve/return (calibrated)": "p_markov_cal_winner",
          "LightGBM": "p_gbm_winner"}
BOOKS = {"Pinnacle": ("psw", "psl"), "Bet365": ("b365w", "b365l"), "Best price": ("maxw", "maxl"),
         "Kaggle odds": ("oddw", "oddl")}


def build(tour: str, start: int, end: int, burn_in: int = 1990) -> pd.DataFrame:
    # Ratings need history before the modelling window to settle.
    matches = sackmann.load(tour, range(min(burn_in, start), end + 1))
    params_path = PARAMS_PATH.with_name(PARAMS_PATH.name.format(tour=tour))
    params = EloParams.load(params_path) if params_path.exists() else EloParams()
    matches = compute_elo(matches, params)  # also sorts chronologically
    matches = compute_serve_return(matches)
    matches = compute_form(matches)
    matches = matches[matches["tourney_date"].dt.year >= start].reset_index(drop=True)

    odds = odds_history.load(tour, range(max(start, 2001), end + 1))
    if odds.empty and tour == "wta":
        odds = odds_kaggle.load(range(start, end + 1))
    if odds.empty:
        print("No odds files available - see ingest/odds_history.py for manual download.")
        joined = matches.assign(odds_matched=False, match_date=pd.NaT,
                                **{c: float("nan") for c in ODDS_COLS})
    else:
        joined = attach_odds(matches, odds)
    joined["match_date"] = joined["match_date"].fillna(joined["tourney_date"])
    return joined


def save(df: pd.DataFrame, tour: str) -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(str(DB_PATH)) as con:
        con.execute(f"CREATE OR REPLACE TABLE {tour}_matches AS SELECT * FROM df")


def evaluate(df: pd.DataFrame, test_years: range) -> None:
    test = df[df["tourney_date"].dt.year.isin(test_years)]
    print(f"\nAll {len(test):,} matches, {test_years.start}-{test_years.stop - 1}")
    for name, col in MODELS.items():
        p, y = symmetric(test[col])
        print(f"  {name:<26} log loss {log_loss(p, y):.4f}  acc {accuracy(p, y):.3f}")

    books = {k: v for k, v in BOOKS.items() if v[0] in test and test[v[0]].notna().any()}
    ref_name, (rw, rl) = next(iter(books.items()))  # sharpest book available
    odds = test.dropna(subset=[rw, rl])
    odds = odds[(odds[rw] > 1) & (odds[rl] > 1)]
    print(f"\n{len(odds):,} matches with {ref_name} odds "
          f"({test['odds_matched'].mean():.1%} of test matches joined to odds)")
    pm, ym = symmetric(proportional(odds[rw], odds[rl]))
    print(f"  {ref_name + ' (margin removed)':<26} log loss {log_loss(pm, ym):.4f}  "
          f"brier {brier(pm, ym):.4f}")
    for name, col in MODELS.items():
        p, y = symmetric(odds[col])
        print(f"  {name:<26} log loss {log_loss(p, y):.4f}  brier {brier(p, y):.4f}")

    print("\nBacktests (bet when model edge over fair price > 3%):")
    for name, col in MODELS.items():
        for book, (w, l) in books.items():
            res = backtest.run(test.assign(p_model=test[col]), w, l)
            print(f"  {name:<26} vs {book:<10} {res.summary()}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tour", default="atp", choices=["atp", "wta"])
    ap.add_argument("--start", type=int, default=2000, help="first year used for training")
    ap.add_argument("--test-from", type=int, default=2020)
    ap.add_argument("--end", type=int, default=2025)
    args = ap.parse_args()

    df = build(args.tour, args.start, args.end)
    test_years = range(args.test_from, args.end + 1)
    p_gbm, p_markov_cal, importance = walk_forward(df, test_years, train_from=args.start)
    df["p_gbm_winner"], df["p_markov_cal_winner"] = p_gbm, p_markov_cal
    save(df, args.tour)

    evaluate(df, test_years)
    print("\nTop features (gain, last model):")
    print((importance / importance.sum()).head(15).round(3).to_string())


if __name__ == "__main__":
    main()
