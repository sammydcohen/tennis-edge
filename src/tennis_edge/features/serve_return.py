"""Opponent-adjusted serve and return ratings, computed strictly in match order.

Model: the share of serve points player A wins against B on surface s is

    serve%(A vs B) = mean(s) + srv(A) - ret(B)

where srv/ret are each player's serve and return strength relative to an average player.
After each match, both observed serve percentages update the four ratings in proportion
to the prediction error, with a learning rate that shrinks as a player gains experience
(the same idea as Elo's K-factor). The surface means are themselves slow running averages,
so nothing here ever sees a future match.

The pre-match serve-point probabilities feed the Markov chain in models/markov.py.
"""

from collections import defaultdict
from dataclasses import dataclass

import numpy as np
import pandas as pd

from tennis_edge.models.markov import match_prob

SURFACE_PRIOR = {"Hard": 0.63, "Clay": 0.60, "Grass": 0.66, "Carpet": 0.65}
MIN_SERVE_POINTS = 20


@dataclass
class ServeParams:
    lr_scale: float = 0.6
    lr_offset: float = 5.0
    lr_shape: float = 0.6
    mean_alpha: float = 0.002  # learning rate of the per-surface average


def _lr(n: int, p: ServeParams) -> float:
    return p.lr_scale / (n + p.lr_offset) ** p.lr_shape


def serve_pct(won1, won2, svpt) -> np.ndarray:
    svpt = np.asarray(svpt, dtype=float)
    with np.errstate(invalid="ignore", divide="ignore"):
        pct = (np.asarray(won1, dtype=float) + np.asarray(won2, dtype=float)) / svpt
    return np.where(svpt >= MIN_SERVE_POINTS, pct, np.nan)


def compute_serve_return(matches: pd.DataFrame, params: ServeParams | None = None) -> pd.DataFrame:
    """Add pre-match serve/return ratings and the Markov win probability for the winner.

    `matches` must already be in chronological order (see features.elo.sort_matches).
    """
    p = params or ServeParams()
    srv: dict = defaultdict(float)
    ret: dict = defaultdict(float)
    n_srv: dict = defaultdict(int)
    n_ret: dict = defaultdict(int)
    mean = dict(SURFACE_PRIOR)

    w_ids = matches["winner_id"].to_numpy()
    l_ids = matches["loser_id"].to_numpy()
    surfaces = matches["surface"].fillna("Hard").to_numpy()
    w_obs = serve_pct(matches["w_1stWon"], matches["w_2ndWon"], matches["w_svpt"])
    l_obs = serve_pct(matches["l_1stWon"], matches["l_2ndWon"], matches["l_svpt"])

    n = len(matches)
    cols = {k: np.empty(n) for k in ("w_srv", "w_ret", "l_srv", "l_ret", "surf_mean")}
    for i in range(n):
        w, l, s = w_ids[i], l_ids[i], surfaces[i]
        m = mean.setdefault(s, 0.63)
        cols["w_srv"][i], cols["w_ret"][i] = srv[w], ret[w]
        cols["l_srv"][i], cols["l_ret"][i] = srv[l], ret[l]
        cols["surf_mean"][i] = m

        # (server, returner, observed serve%)
        for server, returner, obs in ((w, l, w_obs[i]), (l, w, l_obs[i])):
            if np.isnan(obs):
                continue
            err = obs - (m + srv[server] - ret[returner])
            srv[server] += _lr(n_srv[server], p) * err
            ret[returner] -= _lr(n_ret[returner], p) * err
            n_srv[server] += 1
            n_ret[returner] += 1
            mean[s] += p.mean_alpha * (obs - mean[s])

    out = matches.assign(**cols)
    out["pw_serve"] = np.clip(out["surf_mean"] + out["w_srv"] - out["l_ret"], 0.3, 0.95)
    out["pl_serve"] = np.clip(out["surf_mean"] + out["l_srv"] - out["w_ret"], 0.3, 0.95)
    out["p_markov_winner"] = match_prob(out["pw_serve"], out["pl_serve"],
                                        out["best_of"].fillna(3).astype(int))
    return out
