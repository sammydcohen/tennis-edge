"""Search for profitable betting niches without fooling ourselves.

Every candidate segment (one condition x one edge band) is scored on discovery years.
Only segments that were profitable there, with enough bets, are then scored on later
validation years the search never saw. Results are printed alongside how many segments
were tried, so a lone survivor can be judged against what chance alone would produce.

Usage:  uv run python -m tennis_edge.eval.segments
"""

import duckdb
import numpy as np
import pandas as pd

from tennis_edge.betting.backtest import select_bets
from tennis_edge.config import DB_PATH
from tennis_edge.pipeline import BOOKS

DISCOVERY, VALIDATION = range(2020, 2023), range(2023, 2026)
MODELS = {"LightGBM": "p_gbm_winner", "Serve/return": "p_markov_cal_winner", "Elo": "p_elo_winner"}
EDGE_BANDS = {"edge 3-6%": (0.03, 0.06), "edge 6-10%": (0.06, 0.10), "edge 10%+": (0.10, 1.0)}
MIN_BETS = 150


def _side(bets: pd.DataFrame, w: str, l: str) -> pd.Series:
    """Value of a per-player column for the player we bet on."""
    return bets[w].where(bets["side"] == "winner", bets[l])


def conditions(b: pd.DataFrame) -> dict[str, pd.Series]:
    me_days = _side(b, "w_days_off", "l_days_off")
    me_career = _side(b, "w_career", "l_career")
    me_mins = _side(b, "w_tourn_minutes", "l_tourn_minutes")
    opp_mins = _side(b, "l_tourn_minutes", "w_tourn_minutes")
    opp_odds = np.where(b["side"] == "winner", b["_odds_l"], b["_odds_w"])
    conds = {
        "all": pd.Series(True, index=b.index),
        "bet on favourite": b["odds"] < opp_odds,
        "bet on underdog": b["odds"] >= opp_odds,
        "odds < 1.5": b["odds"] < 1.5,
        "odds 1.5-2.5": b["odds"].between(1.5, 2.5),
        "odds > 2.5": b["odds"] > 2.5,
        "early rounds": b["round"].isin(["R128", "R64", "R32"]),
        "late rounds": b["round"].isin(["QF", "SF", "F"]),
        "player back from 60+ day layoff": me_days > 60,
        "player with < 100 career matches": me_career < 100,
        "player fresher by 60+ min this event": (opp_mins - me_mins) >= 60,
    }
    for s in ("Hard", "Clay", "Grass"):
        conds[f"surface {s}"] = b["surface"] == s
    for lvl in b["tourney_level"].dropna().unique():
        conds[f"level {lvl}"] = b["tourney_level"] == lvl
    return conds


def roi_ci(profit: np.ndarray, n_boot: int = 2000, seed: int = 0) -> tuple[float, float]:
    boots = np.random.default_rng(seed).choice(profit, size=(n_boot, len(profit))).mean(axis=1)
    return float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))


def search(df: pd.DataFrame, tour: str) -> tuple[pd.DataFrame, int]:
    rows, tried = [], 0
    for model, col in MODELS.items():
        for book, (w, l) in BOOKS.items():
            if w not in df or df[w].isna().all():
                continue
            d = df.assign(p_model=df[col], _odds_w=df[w], _odds_l=df[l])
            bets = select_bets(d, w, l, min_edge=0.03)
            bets["profit"] = np.where(bets["won"] == 1, bets["odds"] - 1, -1.0)
            year = bets["tourney_date"].dt.year
            for cname, mask in conditions(bets).items():
                for ename, (lo, hi) in EDGE_BANDS.items():
                    seg = mask & bets["edge"].between(lo, hi, inclusive="left")
                    disc = bets.loc[seg & year.isin(DISCOVERY), "profit"].to_numpy()
                    tried += 1
                    if len(disc) < MIN_BETS or disc.mean() <= 0:
                        continue
                    val = bets.loc[seg & year.isin(VALIDATION), "profit"].to_numpy()
                    if len(val) == 0:
                        continue
                    lo_ci, hi_ci = roi_ci(val)
                    rows.append({"tour": tour, "model": model, "book": book, "segment": cname,
                                 "edge": ename, "disc_bets": len(disc), "disc_roi": disc.mean(),
                                 "val_bets": len(val), "val_roi": val.mean(),
                                 "val_ci_low": lo_ci, "val_ci_high": hi_ci})
    return pd.DataFrame(rows), tried


def main() -> None:
    pd.set_option("display.width", 200)
    results, total = [], 0
    with duckdb.connect(str(DB_PATH), read_only=True) as con:
        for tour in ("atp", "wta"):
            df = con.execute(f"SELECT * FROM {tour}_matches WHERE year(tourney_date) >= 2020").df()
            res, tried = search(df, tour)
            results.append(res)
            total += tried
    res = pd.concat(results, ignore_index=True)

    print(f"Segments tried: {total}. Profitable in discovery (>= {MIN_BETS} bets): {len(res)}")
    print(f"Of those, profitable in validation: {(res['val_roi'] > 0).sum()}; "
          f"with 95% CI above zero: {(res['val_ci_low'] > 0).sum()}\n")
    show = res.sort_values("val_roi", ascending=False)
    fmt = {c: "{:+.1%}".format for c in ("disc_roi", "val_roi", "val_ci_low", "val_ci_high")}
    print(show.head(25).to_string(index=False, formatters=fmt))
    print("\nValidation ROI of all discovered segments: "
          f"median {res['val_roi'].median():+.1%}, mean {res['val_roi'].mean():+.1%}")


if __name__ == "__main__":
    main()
