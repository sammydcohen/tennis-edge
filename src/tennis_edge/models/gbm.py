"""LightGBM match model trained walk-forward on Elo, serve/return and form features.

Sackmann rows always list the winner first, so each match is randomly reoriented as
player A vs player B (label: A won). Every test year is predicted by a model trained only
on earlier years, so no prediction ever benefits from data after the match.
"""

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

from tennis_edge.features.elo import ROUND_ORDER

# (winner column, loser column, feature name) pairs that swap when a match is flipped.
PAIRED = [
    ("w_elo", "l_elo", "elo"), ("w_selo", "l_selo", "selo"),
    ("w_srv", "l_srv", "srv"), ("w_ret", "l_ret", "ret"),
    ("pw_serve", "pl_serve", "serve_pt"),
    ("winner_rank", "loser_rank", "rank"), ("winner_rank_points", "loser_rank_points", "rank_pts"),
    ("winner_age", "loser_age", "age"),
    ("w_days_off", "l_days_off", "days_off"), ("w_recent_14d", "l_recent_14d", "recent_14d"),
    ("w_tourn_matches", "l_tourn_matches", "tourn_matches"),
    ("w_tourn_minutes", "l_tourn_minutes", "tourn_minutes"),
    ("w_form", "l_form", "form"), ("w_career", "l_career", "career"), ("w_h2h", "l_h2h", "h2h"),
]
PROBS = ["p_elo_winner", "p_markov_winner"]
CATEGORICAL = ["surface", "tourney_level"]

LGB_PARAMS = {
    "objective": "binary", "learning_rate": 0.03, "num_leaves": 15, "min_data_in_leaf": 200,
    "feature_fraction": 0.8, "bagging_fraction": 0.8, "bagging_freq": 1, "lambda_l2": 5.0,
    "verbose": -1, "seed": 0,
}
NUM_ROUNDS = 400


def _logit(p):
    p = np.clip(np.asarray(p, dtype=float), 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p))


def build_dataset(df: pd.DataFrame, seed: int = 0) -> tuple[pd.DataFrame, np.ndarray, np.ndarray]:
    """Return (features, y, flipped). y = 1 if player A won. flipped = A is the loser."""
    flipped = np.random.default_rng(seed).random(len(df)) < 0.5
    X = pd.DataFrame(index=df.index)
    for wcol, lcol, name in PAIRED:
        w, l = df[wcol].to_numpy(dtype=float), df[lcol].to_numpy(dtype=float)
        X[f"a_{name}"] = np.where(flipped, l, w)
        X[f"b_{name}"] = np.where(flipped, w, l)
        X[f"d_{name}"] = X[f"a_{name}"] - X[f"b_{name}"]
    for col in PROBS:
        p = df[col].to_numpy(dtype=float)
        X[f"logit_{col.removesuffix('_winner')}"] = _logit(np.where(flipped, 1 - p, p))
    X["d_log_rank"] = np.log(X["a_rank"]) - np.log(X["b_rank"])
    X["best_of"] = df["best_of"].to_numpy()
    X["round"] = df["round"].map(ROUND_ORDER).to_numpy()
    for col in CATEGORICAL:
        X[col] = df[col].astype("category")
    return X, (~flipped).astype(int), flipped


def walk_forward(df: pd.DataFrame, test_years: range, train_from: int = 2000):
    """Predict each test year with models trained on [train_from, year).

    Returns per-match probabilities that the *winner* wins, for the GBM and for a
    Platt-calibrated Markov model, plus the feature importance of the last model.
    """
    X, y, flipped = build_dataset(df)
    year = df["tourney_date"].dt.year.to_numpy()
    p_gbm = np.full(len(df), np.nan)
    p_markov_cal = np.full(len(df), np.nan)
    booster = None

    for test_year in test_years:
        train = (year >= train_from) & (year < test_year)
        test = year == test_year
        booster = lgb.train(LGB_PARAMS, lgb.Dataset(X[train], y[train]), NUM_ROUNDS)
        p_a = booster.predict(X[test])
        p_gbm[test] = np.where(flipped[test], 1 - p_a, p_a)

        platt = LogisticRegression(C=1e6).fit(X.loc[train, ["logit_p_markov"]], y[train])
        p_a = platt.predict_proba(X.loc[test, ["logit_p_markov"]])[:, 1]
        p_markov_cal[test] = np.where(flipped[test], 1 - p_a, p_a)

    importance = pd.Series(booster.feature_importance("gain"), index=X.columns)
    return p_gbm, p_markov_cal, importance.sort_values(ascending=False)
