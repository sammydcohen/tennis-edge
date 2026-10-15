"""Grade logged picks by closing line value once their matches have started.

For every pick in the `picks` table (written by models/predict.py) whose match has begun,
the closing price is the last snapshot taken before the start. A pick "beats the close"
when the market's margin-free probability for the picked player rose between the moment
the pick was logged and the start. Over enough picks, consistently beating the close is
the standard evidence that a model has a real edge, long before profit becomes reliable.

Usage:  uv run python -m tennis_edge.betting.clv_tracker
"""

import duckdb
import numpy as np
import pandas as pd

from tennis_edge.betting.vig import proportional
from tennis_edge.config import DB_PATH
from tennis_edge.models.predict import SHARP_BOOKS


def closing_prices(con) -> pd.DataFrame:
    snaps = con.execute("SELECT * FROM odds_snapshots WHERE fetched_at < commence_time").df()
    last = snaps.groupby(["event_id", "bookmaker"])["fetched_at"].transform("max")
    close = snaps[snaps["fetched_at"] == last].dropna(subset=["price_1", "price_2"]).copy()
    close["fair_1"] = proportional(close["price_1"], close["price_2"])
    close["sharp"] = close["bookmaker"].isin(SHARP_BOOKS)
    sharp = close[close["sharp"]].groupby("event_id")["fair_1"].median()
    allb = close.groupby("event_id")["fair_1"].median()
    out = pd.DataFrame({"close_p1": sharp.reindex(allb.index).fillna(allb),
                        "close_fetched": close.groupby("event_id")["fetched_at"].max()})
    return out.reset_index()


def grade() -> pd.DataFrame:
    now = pd.Timestamp.now(tz="UTC").tz_localize(None)
    with duckdb.connect(str(DB_PATH), read_only=True) as con:
        tables = {t for (t,) in con.execute("SHOW TABLES").fetchall()}
        if not {"picks", "odds_snapshots"} <= tables:
            return pd.DataFrame()
        picks = con.execute("SELECT * FROM picks WHERE commence_time < ?", [now]).df()
        close = closing_prices(con)
    g = picks.merge(close, on="event_id")
    g["close_prob"] = np.where(g["pick_side"] == 1, g["close_p1"], 1 - g["close_p1"])
    g["clv_points"] = (g["close_prob"] - g["pick_ref_prob"]) * 100
    g["beat_close"] = g["clv_points"] > 0
    # Price-based CLV: odds we could have taken vs the fair closing odds.
    g["clv_price"] = g["pick_best_odds"] * g["close_prob"] - 1
    return g


def main() -> None:
    g = grade()
    if g.empty:
        print("No graded picks yet: picks are graded once their matches start.")
        return
    print(f"{len(g)} graded picks")
    print(f"  Beat the closing line:    {g['beat_close'].mean():.1%}")
    print(f"  Average CLV:              {g['clv_points'].mean():+.2f} probability points")
    print(f"  Expected ROI at best odds (vs fair close): {g['clv_price'].mean():+.1%}")
    if len(g) >= 30:
        se = g["clv_points"].std() / np.sqrt(len(g))
        print(f"  95% CI on average CLV:    {g['clv_points'].mean() - 1.96 * se:+.2f} to "
              f"{g['clv_points'].mean() + 1.96 * se:+.2f}")


if __name__ == "__main__":
    main()
