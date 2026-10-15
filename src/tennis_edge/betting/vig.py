"""Turn bookmaker decimal odds into fair (margin-free) probabilities."""

import numpy as np


def implied(odds_a, odds_b):
    return 1.0 / np.asarray(odds_a, dtype=float), 1.0 / np.asarray(odds_b, dtype=float)


def overround(odds_a, odds_b):
    ia, ib = implied(odds_a, odds_b)
    return ia + ib - 1.0


def proportional(odds_a, odds_b):
    """Scale implied probabilities so they sum to 1. Returns fair prob of side A."""
    ia, ib = implied(odds_a, odds_b)
    return ia / (ia + ib)


def power(odds_a, odds_b, iters: int = 50):
    """Find k with ia**k + ib**k = 1. Shifts more of the margin onto longshots than
    `proportional`, which matches the favourite-longshot bias seen in tennis markets."""
    ia, ib = implied(odds_a, odds_b)
    lo, hi = np.ones_like(ia), np.full_like(ia, 3.0)
    for _ in range(iters):
        k = (lo + hi) / 2
        too_big = ia**k + ib**k > 1
        lo = np.where(too_big, k, lo)
        hi = np.where(too_big, hi, k)
    return ia ** ((lo + hi) / 2)
