"""Predict upcoming matches from the latest odds snapshots and log model picks.

1. Take every not-yet-started match in `odds_snapshots` (see ingest/odds_live.py).
2. Map player names to known players and infer surface / level from past editions.
3. Append the matches to the history with a placeholder result, so the feature code gives
   them current pre-match ratings (each player's first upcoming match only, so one
   placeholder result can't leak into another prediction).
4. Train LightGBM on all completed matches and score the upcoming ones.
5. Compare with the market and save `upcoming_predictions`. The first time the model
   disagrees with the market by more than MIN_EDGE, the pick is logged to `picks` with the
   price at that moment, so its closing line value can be measured later.

Usage:  uv run python -m tennis_edge.models.predict
"""

import duckdb
import numpy as np
import pandas as pd

from tennis_edge.betting.vig import proportional
from tennis_edge.clean.name_matching import full_name_keys
from tennis_edge.config import DB_PATH
from tennis_edge.ingest.results_bridge import player_index
from tennis_edge.models.gbm import build_dataset, fit_predict
from tennis_edge.pipeline import build

MIN_EDGE = 0.03
SHARP_BOOKS = ("pinnacle", "betfair_ex_eu", "betfair_ex_uk", "matchbook")


def latest_upcoming(con) -> pd.DataFrame:
    now = pd.Timestamp.now(tz="UTC").tz_localize(None)
    snaps = con.execute("SELECT * FROM odds_snapshots WHERE commence_time > ?", [now]).df()
    if snaps.empty:
        return snaps
    first = snaps.groupby(["event_id", "bookmaker"])["fetched_at"].transform("min")
    last = snaps.groupby(["event_id", "bookmaker"])["fetched_at"].transform("max")
    open_ = snaps[snaps["fetched_at"] == first].set_index(["event_id", "bookmaker"])
    latest = snaps[snaps["fetched_at"] == last].set_index(["event_id", "bookmaker"])
    latest["open_1"], latest["open_2"] = open_["price_1"], open_["price_2"]
    return latest.reset_index()


def market_view(prices: pd.DataFrame) -> pd.DataFrame:
    """One row per event: consensus fair prob, sharp fair prob, best prices, opening."""
    p = prices.dropna(subset=["price_1", "price_2"]).copy()
    p["fair_1"] = proportional(p["price_1"], p["price_2"])
    p["open_fair_1"] = proportional(p["open_1"], p["open_2"])
    sharp = p[p["bookmaker"].isin(SHARP_BOOKS)]
    g = p.groupby("event_id")
    view = pd.DataFrame({
        "tour": g["tour"].first(), "tournament": g["tournament"].first(),
        "commence_time": g["commence_time"].first(),
        "player_1": g["player_1"].first(), "player_2": g["player_2"].first(),
        "n_books": g["bookmaker"].nunique(),
        "market_p1": g["fair_1"].median(), "market_open_p1": g["open_fair_1"].median(),
        "best_odds_1": g["price_1"].max(), "best_odds_2": g["price_2"].max(),
        "best_book_1": p.loc[g["price_1"].idxmax(), "bookmaker"].to_numpy(),
        "best_book_2": p.loc[g["price_2"].idxmax(), "bookmaker"].to_numpy(),
    })
    view["sharp_p1"] = sharp.groupby("event_id")["fair_1"].median()
    view["sharp_open_p1"] = sharp.groupby("event_id")["open_fair_1"].median()
    return view.reset_index()


def resolve_players(names: pd.Series, history: pd.DataFrame) -> pd.Series:
    index = player_index(history)
    exact = dict(zip(history["winner_name"], history["winner_id"]))
    exact.update(zip(history["loser_name"], history["loser_id"]))

    def one(name: str):
        if name in exact:
            return str(exact[name])
        for key in full_name_keys(name):
            if key in index:
                return index[key][0]
        return f"NEW:{name}"
    return names.map(one)


def player_profiles(history: pd.DataFrame) -> pd.DataFrame:
    """Latest known rank, ranking points and (projected) age for every player id."""
    long = pd.concat([
        history[["tourney_date", "winner_id", "winner_rank", "winner_rank_points", "winner_age"]]
        .set_axis(["date", "id", "rank", "rank_points", "age"], axis=1),
        history[["tourney_date", "loser_id", "loser_rank", "loser_rank_points", "loser_age"]]
        .set_axis(["date", "id", "rank", "rank_points", "age"], axis=1),
    ]).sort_values("date")
    long["id"] = long["id"].astype(str)
    g = long.groupby("id")
    ranks = g[["rank", "rank_points"]].last()  # last non-null value per player
    aged = long.dropna(subset=["age"]).groupby("id").last()
    years_since = (pd.Timestamp.today() - aged["date"]).dt.days / 365.25
    ranks["age"] = aged["age"] + years_since
    return ranks


def tournament_context(title: str, history: pd.DataFrame) -> dict:
    """Surface, level and best-of from the most recent edition of a similarly named event."""
    words = [w for w in title.replace("-", " ").split()
             if w.upper() not in {"ATP", "WTA", "OPEN", "MASTERS", "CHAMPIONSHIPS", "INTERNATIONAL"}]
    recent = history.sort_values("tourney_date", ascending=False)
    for w in words:
        hit = recent[recent["tourney_name"].str.contains(w, case=False, na=False, regex=False)]
        if len(hit):
            row = hit.iloc[0]
            return {"surface": row["surface"], "tourney_level": row["tourney_level"],
                    "best_of": int(row["best_of"]) if pd.notna(row["best_of"]) else 3}
    return {"surface": "Hard", "tourney_level": "A", "best_of": 3}


def predict_tour(tour: str, events: pd.DataFrame) -> pd.DataFrame:
    year = pd.Timestamp.today().year
    with duckdb.connect(str(DB_PATH), read_only=True) as con:  # built by pipeline --live
        history = con.execute(
            "SELECT tourney_date, tourney_name, surface, tourney_level, best_of, winner_id, "
            "winner_name, loser_id, loser_name, winner_rank, loser_rank, winner_rank_points, "
            f"loser_rank_points, winner_age, loser_age FROM {tour}_matches").df()
    profile = player_profiles(history)
    events = events.copy()
    events["id_1"] = resolve_players(events["player_1"], history)
    events["id_2"] = resolve_players(events["player_2"], history)
    ctx = events["tournament"].map(lambda t: tournament_context(t, history))
    events = pd.concat([events, pd.DataFrame(list(ctx), index=events.index)], axis=1)

    # Score each player's earliest upcoming match only (see module docstring).
    events = events.sort_values("commence_time")
    seen, keep = set(), []
    for _, r in events.iterrows():
        keep.append(r["id_1"] not in seen and r["id_2"] not in seen)
        seen.update((r["id_1"], r["id_2"]))
    events = events[keep]

    today = pd.Timestamp.today().normalize()
    extra = pd.DataFrame({
        "tourney_id": "LIVE-" + events["event_id"], "tourney_name": events["tournament"],
        "surface": events["surface"], "tourney_level": events["tourney_level"],
        "tourney_date": today, "match_num": 0, "best_of": events["best_of"], "round": "R32",
        "winner_id": events["id_1"], "winner_name": events["player_1"],
        "loser_id": events["id_2"], "loser_name": events["player_2"],
        "tour": tour, "upcoming": True, "event_id": events["event_id"],
    })
    for side, col in (("winner", "id_1"), ("loser", "id_2")):
        p = profile.reindex(events[col]).set_index(events.index)
        extra[f"{side}_rank"] = p["rank"]
        extra[f"{side}_rank_points"] = p["rank_points"]
        extra[f"{side}_age"] = p["age"]
    df = build(tour, 2000, year, bridge_to_today=True, extra=extra)
    df["upcoming"] = df["upcoming"].fillna(False).astype(bool)

    X, y, flipped = build_dataset(df)
    train = (~df["upcoming"]).to_numpy()
    test = df["upcoming"].to_numpy()
    p_gbm, p_markov, _ = fit_predict(X, y, flipped, train, test)
    up = df[test]
    return pd.DataFrame({
        "event_id": up["event_id"].to_numpy(),
        "surface": up["surface"].to_numpy(),
        "p1_elo": up["p_elo_winner"].to_numpy(), "p1_serve_return": p_markov,
        "p1_model": p_gbm,
        "elo_1": up["w_elo"].to_numpy(), "elo_2": up["l_elo"].to_numpy(),
        "known_1": ~up["winner_id"].str.startswith("NEW:").to_numpy(),
        "known_2": ~up["loser_id"].str.startswith("NEW:").to_numpy(),
    })


def run() -> pd.DataFrame:
    with duckdb.connect(str(DB_PATH)) as con:
        tables = {t for (t,) in con.execute("SHOW TABLES").fetchall()}
        if "odds_snapshots" not in tables:
            raise SystemExit("No odds snapshots yet. Run: python -m tennis_edge.ingest.odds_live")
        prices = latest_upcoming(con)
    if prices.empty:
        print("No upcoming matches in the latest snapshots.")
        return prices

    market = market_view(prices)
    preds = pd.concat([predict_tour(t, market[market["tour"] == t])
                       for t in market["tour"].unique()], ignore_index=True)
    out = market.merge(preds, on="event_id")
    ref = out["sharp_p1"].fillna(out["market_p1"])  # sharp price when available
    out["reference_p1"] = ref
    out["edge_1"] = out["p1_model"] - ref
    out["pick"] = np.select([out["edge_1"] > MIN_EDGE, out["edge_1"] < -MIN_EDGE],
                            [out["player_1"], out["player_2"]], default=None)
    out["predicted_at"] = pd.Timestamp.now(tz="UTC").tz_localize(None)

    with duckdb.connect(str(DB_PATH)) as con:
        con.execute("CREATE OR REPLACE TABLE upcoming_predictions AS SELECT * FROM out")
        picks = out[out["pick"].notna() & out["known_1"] & out["known_2"]].assign(
            pick_side=lambda d: np.where(d["pick"] == d["player_1"], 1, 2),
            pick_prob=lambda d: np.where(d["pick_side"] == 1, d["p1_model"], 1 - d["p1_model"]),
            pick_ref_prob=lambda d: np.where(d["pick_side"] == 1, d["reference_p1"],
                                             1 - d["reference_p1"]),
            pick_best_odds=lambda d: np.where(d["pick_side"] == 1, d["best_odds_1"],
                                              d["best_odds_2"]),
        )[["event_id", "tour", "tournament", "commence_time", "player_1", "player_2", "pick",
           "pick_side", "pick_prob", "pick_ref_prob", "pick_best_odds", "predicted_at"]]
        con.register("picks_df", picks)
        con.execute("CREATE TABLE IF NOT EXISTS picks AS SELECT * FROM picks_df LIMIT 0")
        # Log each event once, at the first time the model flagged it.
        con.execute("INSERT INTO picks SELECT * FROM picks_df "
                    "WHERE event_id NOT IN (SELECT event_id FROM picks)")
    print(f"Predicted {len(out)} upcoming matches; {out['pick'].notna().sum()} where the model "
          f"disagrees with the market by more than {MIN_EDGE:.0%}.")
    return out


if __name__ == "__main__":
    run()
