"""Overall + surface-specific Elo ratings, computed strictly in match order.

Every match gets the *pre-match* ratings of both players, so the outputs are safe to use
as features (no lookahead). K-factor decays with experience, following FiveThirtyEight's
tennis Elo: K = k_scale / (n_matches + k_offset) ** k_shape.
"""

from collections import defaultdict
from dataclasses import dataclass

import numpy as np
import pandas as pd

ROUND_ORDER = {
    "Q1": 0, "Q2": 1, "Q3": 2, "Q4": 3, "ER": 4, "RR": 5, "R128": 6, "R64": 7, "R32": 8,
    "R16": 9, "QF": 10, "SF": 11, "BR": 12, "F": 13,
}


@dataclass
class EloParams:
    start: float = 1500.0
    k_scale: float = 250.0
    k_offset: float = 5.0
    k_shape: float = 0.4
    surface_weight: float = 0.5  # blend between overall and surface rating for predictions


def expected(r_a: float, r_b: float) -> float:
    return 1.0 / (1.0 + 10 ** ((r_b - r_a) / 400.0))


def k_factor(n: int, p: EloParams) -> float:
    return p.k_scale / (n + p.k_offset) ** p.k_shape


def sort_matches(matches: pd.DataFrame) -> pd.DataFrame:
    order = matches["round"].map(ROUND_ORDER).fillna(5)
    return (
        matches.assign(_round_order=order)
        .sort_values(["tourney_date", "tourney_id", "_round_order", "match_num"], kind="stable")
        .drop(columns="_round_order")
        .reset_index(drop=True)
    )


def compute_elo(matches: pd.DataFrame, params: EloParams | None = None) -> pd.DataFrame:
    """Return `matches` (sorted) with pre-match Elo columns and the Elo win prob for the winner."""
    p = params or EloParams()
    matches = sort_matches(matches)
    rating: dict = defaultdict(lambda: p.start)
    surf_rating: dict = defaultdict(lambda: p.start)
    count: dict = defaultdict(int)
    surf_count: dict = defaultdict(int)

    n = len(matches)
    out = {k: np.empty(n) for k in ("w_elo", "l_elo", "w_selo", "l_selo")}
    w_ids = matches["winner_id"].to_numpy()
    l_ids = matches["loser_id"].to_numpy()
    surfaces = matches["surface"].fillna("Unknown").to_numpy()

    for i in range(n):
        w, l, s = w_ids[i], l_ids[i], surfaces[i]
        ws, ls = (w, s), (l, s)
        out["w_elo"][i], out["l_elo"][i] = rating[w], rating[l]
        out["w_selo"][i], out["l_selo"][i] = surf_rating[ws], surf_rating[ls]

        e = expected(rating[w], rating[l])
        rating[w] += k_factor(count[w], p) * (1 - e)
        rating[l] -= k_factor(count[l], p) * (1 - e)
        count[w] += 1
        count[l] += 1

        es = expected(surf_rating[ws], surf_rating[ls])
        surf_rating[ws] += k_factor(surf_count[ws], p) * (1 - es)
        surf_rating[ls] -= k_factor(surf_count[ls], p) * (1 - es)
        surf_count[ws] += 1
        surf_count[ls] += 1

    result = matches.assign(**out)
    blend_w = (1 - p.surface_weight) * result["w_elo"] + p.surface_weight * result["w_selo"]
    blend_l = (1 - p.surface_weight) * result["l_elo"] + p.surface_weight * result["l_selo"]
    result["p_elo_winner"] = 1.0 / (1.0 + 10 ** ((blend_l - blend_w) / 400.0))
    return result
