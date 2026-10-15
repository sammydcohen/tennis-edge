import numpy as np
import pandas as pd
import pytest

from tennis_edge.betting import backtest
from tennis_edge.betting.kelly import kelly_fraction
from tennis_edge.betting.vig import overround, power, proportional


def test_proportional_removes_margin():
    p = proportional(1.80, 2.10)
    assert 0 < p < 1
    assert overround(1.80, 2.10) == pytest.approx(1 / 1.8 + 1 / 2.1 - 1)
    assert p + proportional(2.10, 1.80) == pytest.approx(1.0)


def test_power_sums_to_one_and_favours_favourite():
    pa, pb = power(np.array([1.30]), np.array([3.60])), power(np.array([3.60]), np.array([1.30]))
    assert pa + pb == pytest.approx(1.0, abs=1e-6)
    assert pa[0] > proportional(1.30, 3.60)


def test_fair_odds_unchanged():
    assert proportional(2.0, 2.0) == pytest.approx(0.5)


def test_kelly():
    # p=0.55 at evens: full Kelly = 0.10, quarter = 0.025.
    assert kelly_fraction(0.55, 2.0, fraction=0.25) == pytest.approx(0.025)
    assert kelly_fraction(0.40, 2.0) == 0.0
    assert kelly_fraction(0.99, 2.0, fraction=1.0, cap=0.05) == 0.05


def test_backtest_bets_value_side_only():
    df = pd.DataFrame({
        "match_date": pd.to_datetime(["2024-01-01", "2024-01-02"]),
        "p_model": [0.70, 0.50],  # first: model likes winner vs fair 0.5; second: no edge
        "psw": [2.0, 2.0],
        "psl": [2.0, 2.0],
    })
    res = backtest.run(df, min_edge=0.03, n_boot=10)
    assert res.n_bets == 1
    assert res.bets.iloc[0]["side"] == "winner"
    assert res.roi == pytest.approx(1.0)
