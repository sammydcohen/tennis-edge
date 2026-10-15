"""Tune Elo parameters by coordinate descent on log loss.

Ratings are always run over the full history (from 1990) so they have time to settle,
but parameters are *chosen* using only train-year matches and then reported once on
held-out test years.

Usage:  uv run python -m tennis_edge.models.tune_elo --tour atp
"""

import argparse
from dataclasses import replace

import pandas as pd

from tennis_edge.eval.metrics import accuracy, log_loss, symmetric
from tennis_edge.features.elo import EloParams, compute_elo, sort_matches
from tennis_edge.ingest import sackmann
from tennis_edge.config import ROOT

PARAMS_PATH = ROOT / "src" / "tennis_edge" / "models" / "elo_params_{tour}.json"

GRID = {
    "surface_weight": [0.0, 0.2, 0.35, 0.5, 0.65, 0.8],
    "k_scale": [150, 200, 250, 300, 350, 450],
    "k_offset": [2, 5, 10, 20],
    "k_shape": [0.3, 0.4, 0.5],
    "slam_k_mult": [1.0, 1.1, 1.2, 1.35, 1.5],
    "layoff_days": [45, 60, 90, 120],
    "layoff_shrink": [0.0, 0.02, 0.05, 0.1, 0.15],
}


def score(rated: pd.DataFrame, years: range) -> tuple[float, float]:
    sub = rated[rated["tourney_date"].dt.year.isin(years)]
    p, y = symmetric(sub["p_elo_winner"])
    return log_loss(p, y), accuracy(p, y)


def evaluate(matches, params, train, test):
    rated = compute_elo(matches, params)
    return score(rated, train), score(rated, test)


def coordinate_descent(matches, start: EloParams, keys, train, passes=2) -> EloParams:
    best = start
    best_ll = evaluate(matches, best, train, train)[0][0]
    for _ in range(passes):
        improved = False
        for key in keys:
            for value in GRID[key]:
                cand = replace(best, **{key: value})
                ll = evaluate(matches, cand, train, train)[0][0]
                if ll < best_ll - 1e-6:
                    best, best_ll, improved = cand, ll, True
        if not improved:
            break
    return best


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tour", default="atp", choices=["atp", "wta"])
    args = ap.parse_args()
    train, test = range(2010, 2020), range(2020, 2026)

    matches = sort_matches(sackmann.load(args.tour, range(1990, 2026)))

    # Add one idea at a time so the README can show what each one is worth.
    stages = [
        ("Baseline (FiveThirtyEight constants)", []),
        ("+ tuned surface blend", ["surface_weight"]),
        ("+ tuned K-factor", ["surface_weight", "k_scale", "k_offset", "k_shape"]),
        ("+ Grand Slam weighting", ["slam_k_mult"]),
        ("+ layoff decay", ["layoff_days", "layoff_shrink"]),
    ]
    params = EloParams()
    rows = []
    for name, keys in stages:
        if keys:
            params = coordinate_descent(matches, params, keys, train)
        (tr_ll, tr_acc), (te_ll, te_acc) = evaluate(matches, params, train, test)
        rows.append({"stage": name, "train_logloss": tr_ll, "test_logloss": te_ll,
                     "test_acc": te_acc})
        print(f"{name:<40} train {tr_ll:.4f}  test {te_ll:.4f}  acc {te_acc:.3f}", flush=True)

    print("\nBest params:", params)
    path = PARAMS_PATH.with_name(PARAMS_PATH.name.format(tour=args.tour))
    params.save(path)
    print(f"Saved to {path}")
    print("\n| Stage | Train log loss | Test log loss | Test accuracy |\n|---|---|---|---|")
    for r in rows:
        print(f"| {r['stage']} | {r['train_logloss']:.4f} | {r['test_logloss']:.4f} "
              f"| {r['test_acc']:.1%} |")


if __name__ == "__main__":
    main()
