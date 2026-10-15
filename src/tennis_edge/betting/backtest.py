"""Flat-stake and Kelly backtests of model probabilities against bookmaker odds.

Input rows are matches with `p_model` = model probability that the *winner* wins, and
decimal odds for the winner/loser. Both sides of every match are considered; a bet is
placed on whichever side's edge over the fair market price exceeds `min_edge`.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from tennis_edge.betting.kelly import kelly_fraction
from tennis_edge.betting.vig import proportional


@dataclass
class BacktestResult:
    bets: pd.DataFrame
    n_bets: int
    roi: float
    roi_ci: tuple[float, float]
    final_bankroll: float
    max_drawdown: float

    def summary(self) -> dict:
        return {
            "n_bets": self.n_bets,
            "roi": round(self.roi, 4),
            "roi_95ci": tuple(round(x, 4) for x in self.roi_ci),
            "final_bankroll": round(self.final_bankroll, 3),
            "max_drawdown": round(self.max_drawdown, 4),
        }


def select_bets(df: pd.DataFrame, odds_w: str, odds_l: str, min_edge: float = 0.03,
                max_odds: float = 5.0) -> pd.DataFrame:
    d = df.dropna(subset=[odds_w, odds_l, "p_model"]).copy()
    d = d[(d[odds_w] > 1) & (d[odds_l] > 1)]
    fair_w = proportional(d[odds_w], d[odds_l])
    sides = []
    for side, p, fair, odds, won in (
        ("winner", d["p_model"], fair_w, d[odds_w], 1),
        ("loser", 1 - d["p_model"], 1 - fair_w, d[odds_l], 0),
    ):
        s = d.assign(side=side, p_bet=p, p_fair=fair, odds=odds, won=won)
        s["edge"] = s["p_bet"] - s["p_fair"]
        sides.append(s[(s["edge"] > min_edge) & (s["odds"] <= max_odds)])
    bets = pd.concat(sides).sort_values("match_date", kind="stable")
    # Never bet both sides of one match.
    return bets.loc[~bets.index.duplicated(keep="first")]


def run(df: pd.DataFrame, odds_w: str = "psw", odds_l: str = "psl", min_edge: float = 0.03,
        kelly: float = 0.25, n_boot: int = 2000, seed: int = 0) -> BacktestResult:
    bets = select_bets(df, odds_w, odds_l, min_edge=min_edge)
    profit_flat = np.where(bets["won"] == 1, bets["odds"] - 1, -1.0)
    bets = bets.assign(profit_flat=profit_flat)

    stakes = kelly_fraction(bets["p_bet"], bets["odds"], fraction=kelly)
    bankroll, curve = 1.0, []
    for f, pr in zip(stakes, profit_flat):
        bankroll += bankroll * f * pr
        curve.append(bankroll)
    curve = np.array(curve) if curve else np.array([1.0])
    drawdown = float(np.max(1 - curve / np.maximum.accumulate(curve)))
    bets = bets.assign(bankroll=curve[: len(bets)])

    rng = np.random.default_rng(seed)
    if len(bets):
        boots = rng.choice(profit_flat, size=(n_boot, len(profit_flat))).mean(axis=1)
        ci = (float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5)))
        roi = float(profit_flat.mean())
    else:
        ci, roi = (0.0, 0.0), 0.0
    return BacktestResult(bets, len(bets), roi, ci, float(curve[-1]), drawdown)
