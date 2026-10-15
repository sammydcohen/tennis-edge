"""Point-level Markov model: serve-point win probabilities -> game -> set -> match.

`pa` is the probability player A wins a point on A's own serve; `pb` the same for B.
Assumes points are i.i.d. given the server, which is the classic (Barnett & Clarke) model.
"""

from functools import lru_cache


def p_game(p: float) -> float:
    """Probability the server holds, from point-win probability p on serve."""
    q = 1 - p
    deuce = p * p / (p * p + q * q) if p not in (0, 1) else p
    # Win 4-0, 4-1, 4-2, or reach 3-3 and win from deuce.
    return p**4 * (1 + 4 * q + 10 * q * q) + 20 * p**3 * q**3 * deuce


def p_tiebreak(pa: float, pb: float, target: int = 7) -> float:
    """Probability A wins a tiebreak that A serves first (serve order: A, B, B, A, A, ...)."""

    @lru_cache(maxsize=None)
    def win(a: int, b: int) -> float:
        if a >= target and a - b >= 2:
            return 1.0
        if b >= target and b - a >= 2:
            return 0.0
        if a == b and a >= target - 1:
            # Two points from deuce-like state; server pattern repeats every 2 points.
            a_wins_pair = pa * (1 - pb)
            b_wins_pair = (1 - pa) * pb
            return a_wins_pair / (a_wins_pair + b_wins_pair) if a_wins_pair + b_wins_pair else 0.5
        point = a + b
        a_serving = ((point + 1) // 2) % 2 == 0
        p = pa if a_serving else 1 - pb
        return p * win(a + 1, b) + (1 - p) * win(a, b + 1)

    return win(0, 0)


def p_set(pa: float, pb: float) -> float:
    """Probability A wins a standard tiebreak set, with A serving the first game."""
    ga, gb = p_game(pa), p_game(pb)
    tb = p_tiebreak(pa, pb)

    @lru_cache(maxsize=None)
    def win(a: int, b: int) -> float:
        if a >= 6 and a - b >= 2:
            return 1.0
        if b >= 6 and b - a >= 2:
            return 0.0
        if a == 6 and b == 6:
            return tb
        a_serving = (a + b) % 2 == 0
        p = ga if a_serving else 1 - gb
        return p * win(a + 1, b) + (1 - p) * win(a, b + 1)

    return win(0, 0)


def p_match(pa: float, pb: float, best_of: int = 3) -> float:
    """Probability A wins the match. Averages over who serves first in each set."""
    s = 0.5 * (p_set(pa, pb) + (1 - p_set(pb, pa)))
    need = best_of // 2 + 1

    @lru_cache(maxsize=None)
    def win(a: int, b: int) -> float:
        if a == need:
            return 1.0
        if b == need:
            return 0.0
        return s * win(a + 1, b) + (1 - s) * win(a, b + 1)

    return win(0, 0)
