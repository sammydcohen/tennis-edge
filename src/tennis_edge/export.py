"""Export everything the website shows as static JSON files in web/public/data/.

The site has no backend: it reads these files at build time (and the live page re-fetches
them), so refreshing the data is just re-running this module after the pipeline.

Usage:  uv run python -m tennis_edge.export
"""

import json

import duckdb
import numpy as np
import pandas as pd

from tennis_edge.betting import backtest
from tennis_edge.betting.backtest import select_bets
from tennis_edge.betting.clv_tracker import grade
from tennis_edge.betting.vig import proportional
from tennis_edge.config import DB_PATH, ROOT
from tennis_edge.eval import clv, segments
from tennis_edge.eval.metrics import accuracy, brier, calibration_table, log_loss, symmetric
from tennis_edge.features.elo import EloParams
from tennis_edge.models.tune_elo import PARAMS_PATH

OUT = ROOT / "web" / "public" / "data"
MODELS = {"elo": "p_elo_winner", "serve_return": "p_markov_cal_winner", "lightgbm": "p_gbm_winner"}
REF_BOOK = {"atp": ("psw", "psl", "Pinnacle"), "wta": ("oddw", "oddl", "Bookmaker")}
HIST_YEARS = range(2020, 2026)


def _clean(obj):
    """Make numpy / pandas values JSON-safe; NaN becomes null."""
    if isinstance(obj, dict):
        return {k: _clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_clean(v) for v in obj]
    if isinstance(obj, (np.floating, float)):
        return None if not np.isfinite(obj) else round(float(obj), 5)
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, (pd.Timestamp, np.datetime64)):
        return pd.Timestamp(obj).isoformat()
    return obj


def write(name: str, data) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{name}.json").write_text(json.dumps(_clean(data), separators=(",", ":")))


def model_scores(df: pd.DataFrame, w: str, l: str) -> dict:
    odds = df.dropna(subset=[w, l])
    odds = odds[(odds[w] > 1) & (odds[l] > 1)]
    pm, ym = symmetric(proportional(odds[w], odds[l]))
    out = {"n_matches": len(df), "n_with_odds": len(odds),
           "market": {"log_loss": log_loss(pm, ym), "brier": brier(pm, ym)}}
    for key, col in MODELS.items():
        p, y = symmetric(odds[col])
        pa, ya = symmetric(df[col])
        res = backtest.run(df.assign(p_model=df[col]), w, l, n_boot=1000)
        out[key] = {"log_loss": log_loss(p, y), "brier": brier(p, y), "accuracy": accuracy(pa, ya),
                    "roi": res.roi, "roi_ci": list(res.roi_ci), "bets": res.n_bets}
    return out


def equity_curves(df: pd.DataFrame, w: str, l: str, points: int = 160) -> dict:
    curves = {}
    for key, col in MODELS.items():
        bets = select_bets(df.assign(p_model=df[col]), w, l, min_edge=0.03)
        profit = np.where(bets["won"] == 1, bets["odds"] - 1, -1.0)
        cum = np.cumsum(profit)
        idx = np.linspace(0, len(cum) - 1, min(points, len(cum))).astype(int)
        curves[key] = [{"date": bets["match_date"].iloc[i].strftime("%Y-%m-%d"), "bet": int(i + 1),
                        "units": cum[i]} for i in idx]
    return curves


def edge_buckets(df: pd.DataFrame, w: str, l: str) -> list[dict]:
    bets = select_bets(df.assign(p_model=df["p_gbm_winner"]), w, l, min_edge=0.0)
    bets["profit"] = np.where(bets["won"] == 1, bets["odds"] - 1, -1.0)
    labels = ["0-3%", "3-6%", "6-10%", "10-15%", "15%+"]
    bets["bucket"] = pd.cut(bets["edge"], [0, 0.03, 0.06, 0.10, 0.15, 1], labels=labels)
    g = bets.groupby("bucket", observed=True)["profit"].agg(["count", "mean"])
    return [{"bucket": b, "bets": int(r["count"]), "roi": r["mean"]} for b, r in g.iterrows()]


def calibration(df: pd.DataFrame) -> list[dict]:
    p, y = symmetric(df["p_gbm_winner"])
    cal = calibration_table(p, y, bins=10)
    return [{"predicted": r.mean_pred, "observed": r.observed, "n": int(r.n)}
            for r in cal.itertuples()]


def rankings(df: pd.DataFrame, top: int = 50) -> list[dict]:
    long = pd.concat([
        df[["match_date", "winner_id", "winner_name", "w_elo", "w_selo", "surface", "winner_rank"]]
        .set_axis(["date", "id", "name", "elo", "selo", "surface", "rank"], axis=1).assign(won=1),
        df[["match_date", "loser_id", "loser_name", "l_elo", "l_selo", "surface", "loser_rank"]]
        .set_axis(["date", "id", "name", "elo", "selo", "surface", "rank"], axis=1).assign(won=0),
    ]).sort_values("date")
    cutoff = long["date"].max() - pd.Timedelta(days=180)
    active = long[long["date"] >= cutoff].groupby("id").size()
    active = active[active >= 8].index
    last = long[long["id"].isin(active)].groupby("id").last()
    board = last.sort_values("elo", ascending=False).head(top)
    out = []
    for pid, r in board.iterrows():
        mine = long[long["id"] == pid]
        surf = mine.groupby("surface")["selo"].last()
        monthly = mine.set_index("date")["elo"].resample("MS").last().dropna().tail(36)
        recent = mine.tail(10)
        out.append({
            "id": str(pid), "name": r["name"], "elo": r["elo"], "atp_rank": r["rank"],
            "hard": surf.get("Hard"), "clay": surf.get("Clay"), "grass": surf.get("Grass"),
            "form": recent["won"].tolist(), "last_match": r["date"].strftime("%Y-%m-%d"),
            "history": [{"month": d.strftime("%Y-%m"), "elo": v} for d, v in monthly.items()],
        })
    return out


def segment_summary() -> dict:
    results, tried = [], 0
    with duckdb.connect(str(DB_PATH), read_only=True) as con:
        for tour in ("atp", "wta"):
            df = con.execute(f"SELECT * FROM {tour}_matches WHERE year(tourney_date) BETWEEN "
                             "2020 AND 2025").df()
            res, n = segments.search(df, tour)
            results.append(res)
            tried += n
    res = pd.concat(results, ignore_index=True)
    top = res.sort_values("val_roi", ascending=False).head(12)
    return {"tried": tried, "discovered": len(res), "validated_positive": int((res["val_roi"] > 0).sum()),
            "validated_significant": int((res["val_ci_low"] > 0).sum()),
            "discovered_median_val_roi": res["val_roi"].median(),
            "top": top.to_dict("records")}


def clv_summary() -> list[dict]:
    df = clv.join_predictions(clv.load_snapshots())
    rows = []
    for (tour, book), g in df.groupby(["tour", "bookmaker_name"]):
        if len(g) < 100:
            continue
        a = clv.analyse(g)
        lgbm = a[a["model"] == "LightGBM"].iloc[0]
        rows.append({"tour": tour, "book": book, "matches": len(g), "bets": lgbm["bets"],
                     "toward": lgbm["moved toward us"], "against": lgbm["moved against"],
                     "avg_move": lgbm["avg move (prob pts)"], "corr": lgbm["corr(edge, move)"],
                     "roi": lgbm["ROI at opening odds"]})
    return rows


def upcoming() -> list[dict]:
    with duckdb.connect(str(DB_PATH), read_only=True) as con:
        tables = {t for (t,) in con.execute("SHOW TABLES").fetchall()}
        if "upcoming_predictions" not in tables:
            return []
        up = con.execute("SELECT * FROM upcoming_predictions ORDER BY commence_time").df()
    now = pd.Timestamp.now(tz="UTC").tz_localize(None)
    return up[up["commence_time"] > now].to_dict("records")


def main() -> None:
    summary = {"generated_at": pd.Timestamp.now(tz="UTC").isoformat(), "tours": {}}
    with duckdb.connect(str(DB_PATH), read_only=True) as con:
        for tour in ("atp", "wta"):
            df = con.execute(f"SELECT * FROM {tour}_matches").df()
            w, l, book = REF_BOOK[tour]
            hist = df[df["tourney_date"].dt.year.isin(HIST_YEARS)]
            unseen = df[df["bridged"].fillna(False).astype(bool)]
            params = EloParams.load(PARAMS_PATH.with_name(PARAMS_PATH.name.format(tour=tour)))
            summary["tours"][tour] = {
                "reference_book": book,
                "total_matches": len(df), "first_year": int(df["tourney_date"].dt.year.min()),
                "last_result": df["match_date"].max(),
                "historical": model_scores(hist, w, l),
                "unseen": model_scores(unseen, "oddw", "oddl") if len(unseen) else None,
                "unseen_range": [unseen["match_date"].min(), unseen["match_date"].max()],
                "elo_params": params.__dict__,
            }
            write(f"{tour}_equity", equity_curves(hist, w, l))
            write(f"{tour}_edge_buckets", edge_buckets(hist, w, l))
            write(f"{tour}_calibration", calibration(hist))
            write(f"{tour}_rankings", rankings(df))
    write("summary", summary)
    write("segments", segment_summary())
    write("clv", clv_summary())
    write("upcoming", upcoming())
    tracker = grade()
    write("tracker", {
        "graded": len(tracker),
        "beat_close": tracker["beat_close"].mean() if len(tracker) else None,
        "avg_clv": tracker["clv_points"].mean() if len(tracker) else None,
        "picks": tracker.sort_values("commence_time", ascending=False).head(100).to_dict("records")
        if len(tracker) else [],
    })
    print(f"Wrote site data to {OUT}")


if __name__ == "__main__":
    main()
