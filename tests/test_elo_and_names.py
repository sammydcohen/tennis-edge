import pandas as pd
import pytest

from tennis_edge.clean.name_matching import attach_odds, full_name_keys, odds_name_key
from tennis_edge.features.elo import compute_elo, expected


def _matches(rows):
    return pd.DataFrame(rows, columns=[
        "tour", "tourney_id", "tourney_date", "match_num", "round", "surface",
        "winner_id", "winner_name", "loser_id", "loser_name",
    ]).assign(tourney_date=lambda d: pd.to_datetime(d["tourney_date"]))


def test_expected():
    assert expected(1500, 1500) == 0.5
    assert expected(1600, 1500) == pytest.approx(0.640, abs=1e-3)


def test_elo_uses_pre_match_ratings_only():
    m = _matches([
        ("atp", "t1", "2024-01-01", 2, "F", "Hard", 1, "A", 2, "B"),
        ("atp", "t1", "2024-01-01", 1, "SF", "Hard", 1, "A", 3, "C"),
    ])
    out = compute_elo(m)
    # Sorted by round: SF first, at default ratings.
    assert list(out["round"]) == ["SF", "F"]
    assert out.loc[0, "w_elo"] == 1500 and out.loc[0, "p_elo_winner"] == 0.5
    # In the final A carries the rating gained in the SF; B is still fresh.
    assert out.loc[1, "w_elo"] > 1500 and out.loc[1, "l_elo"] == 1500


def test_elo_unchanged_by_future_rows():
    base = [("atp", "t1", "2024-01-01", 1, "R32", "Clay", 1, "A", 2, "B")]
    future = [("atp", "t2", "2024-02-01", 1, "R32", "Clay", 2, "B", 1, "A")]
    a = compute_elo(_matches(base))
    b = compute_elo(_matches(base + future))
    assert a.loc[0, "p_elo_winner"] == b.loc[0, "p_elo_winner"]


@pytest.mark.parametrize("odds_name,full_name", [
    ("Djokovic N.", "Novak Djokovic"),
    ("Del Potro J.M.", "Juan Martin del Potro"),
    ("Auger-Aliassime F.", "Felix Auger-Aliassime"),
    ("Carreno Busta P.", "Pablo Carreno Busta"),
    ("Monfils G.", "Gaël Monfils"),
])
def test_name_keys(odds_name, full_name):
    assert odds_name_key(odds_name) in full_name_keys(full_name)


def test_attach_odds_respects_date_window():
    m = _matches([
        ("atp", "t1", "2024-01-01", 1, "F", "Hard", 1, "Novak Djokovic", 2, "Rafael Nadal"),
        ("atp", "t2", "2024-06-01", 1, "F", "Clay", 1, "Novak Djokovic", 2, "Rafael Nadal"),
    ])
    odds = pd.DataFrame({
        "tour": ["atp"], "date": pd.to_datetime(["2024-06-08"]),
        "winner": ["Djokovic N."], "loser": ["Nadal R."], "psw": [1.9], "psl": [1.95],
    })
    out = attach_odds(m, odds)
    assert out["odds_matched"].tolist() == [False, True]
    assert out.loc[1, "psw"] == 1.9
