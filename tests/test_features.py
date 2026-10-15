import numpy as np
import pandas as pd
import pytest

from tennis_edge.features.elo import sort_matches
from tennis_edge.features.form import compute_form
from tennis_edge.features.serve_return import compute_serve_return
from tennis_edge.models.gbm import PAIRED, build_dataset
from tennis_edge.models.markov import match_prob, p_match


def _matches(rows):
    """rows: (tourney_id, date, round, winner, loser, w_serve_won, l_serve_won)"""
    df = pd.DataFrame(rows, columns=["tourney_id", "tourney_date", "round", "winner_id",
                                     "loser_id", "w_won", "l_won"])
    return sort_matches(df.assign(
        tour="atp", tourney_date=pd.to_datetime(df["tourney_date"]), match_num=1,
        surface="Hard", best_of=3, minutes=90.0,
        w_svpt=100, w_1stWon=df["w_won"], w_2ndWon=0,
        l_svpt=100, l_1stWon=df["l_won"], l_2ndWon=0,
    ).drop(columns=["w_won", "l_won"]))


def test_match_prob_matches_exact_model():
    for pa, pb, bo in [(0.655, 0.613, 3), (0.71, 0.58, 5), (0.6, 0.6, 3)]:
        assert match_prob([pa], [pb], [bo])[0] == pytest.approx(p_match(pa, pb, bo), abs=2e-3)


def test_serve_ratings_update_in_the_right_direction():
    rows = [("t1", "2024-01-01", "R32", "A", "B", 75, 55),
            ("t2", "2024-02-01", "R32", "A", "C", 70, 60)]
    out = compute_serve_return(_matches(rows))
    first, second = out.iloc[0], out.iloc[1]
    assert first["w_srv"] == 0 and first["p_markov_winner"] == pytest.approx(0.5, abs=1e-3)
    # A served well and returned well in match 1, so both ratings rise before match 2.
    assert second["w_srv"] > 0 and second["w_ret"] > 0
    assert second["p_markov_winner"] > 0.5


def test_serve_ratings_ignore_future_matches():
    base = [("t1", "2024-01-01", "R32", "A", "B", 75, 55)]
    future = [("t2", "2024-05-01", "R32", "B", "A", 80, 50)]
    a = compute_serve_return(_matches(base))
    b = compute_serve_return(_matches(base + future))
    assert a.iloc[0]["p_markov_winner"] == b.iloc[0]["p_markov_winner"]


def test_form_counts_only_earlier_matches():
    rows = [("t1", "2024-01-01", "R32", "A", "B", 70, 60),
            ("t1", "2024-01-01", "R16", "A", "C", 70, 60),
            ("t2", "2024-01-08", "R32", "B", "A", 70, 60)]
    out = compute_form(_matches(rows))
    assert out.loc[0, "w_tourn_matches"] == 0 and out.loc[0, "w_career"] == 0
    assert out.loc[1, "w_tourn_matches"] == 1 and out.loc[1, "w_tourn_minutes"] == 90
    assert out.loc[1, "w_form"] > 0.5
    # Match 3: A (now the loser) played twice in last week's event; B lost to A before.
    assert out.loc[2, "l_recent_14d"] == 2 and out.loc[2, "l_tourn_matches"] == 0
    assert out.loc[2, "l_h2h"] == 1 and out.loc[2, "w_h2h"] == 0
    assert out.loc[2, "l_days_off"] == 7


def test_dataset_flip_is_consistent():
    n = 200
    df = pd.DataFrame({c: np.arange(n, dtype=float) + (1000 if c.startswith(("w_", "winner", "pw"))
                                                          else 0)
                       for pair in PAIRED for c in pair[:2]})
    df = df.assign(p_elo_winner=0.7, p_markov_winner=0.6, best_of=3, round="F",
                   surface="Hard", tourney_level="A",
                   tourney_date=pd.Timestamp("2024-01-01"))
    X, y, flipped = build_dataset(df)
    assert 0.3 < flipped.mean() < 0.7
    # Player A is the winner exactly when y == 1, and features follow the players.
    assert ((X["d_elo"] > 0) == (y == 1)).all()
    assert np.allclose(X.loc[y == 1, "logit_p_elo"], np.log(0.7 / 0.3))
    assert np.allclose(X.loc[y == 0, "logit_p_elo"], np.log(0.3 / 0.7))
