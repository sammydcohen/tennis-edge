import numpy as np


def kelly_fraction(p, odds, fraction: float = 0.25, cap: float = 0.05):
    """Fraction of bankroll to stake on a bet at decimal `odds` with win prob `p`.

    Uses fractional Kelly (default quarter Kelly) and caps any single stake, since model
    probabilities are noisy and full Kelly on overestimated edges ruins bankrolls.
    """
    p = np.asarray(p, dtype=float)
    b = np.asarray(odds, dtype=float) - 1.0
    f = (b * p - (1 - p)) / b
    return np.clip(f * fraction, 0.0, cap)
