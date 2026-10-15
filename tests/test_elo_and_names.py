import pandas as pd
import pytest

from tennis_edge.clean.name_matching import attach_odds, full_name_keys, odds_name_key
from tennis_edge.features.elo import EloParams, compute_elo, expected


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


def test_slam_weighting_moves_ratings_more():
    rows = [("atp", "t1", "2024-01-01", 1, "F", "Hard", 1, "A", 2, "B")]
    normal = compute_elo(_matches(rows).assign(tourney_level="G"))
    boosted = compute_elo(_matches(rows + rows).assign(tourney_level="G"),
                          EloParams(slam_k_mult=1.5))
    base = compute_elo(_matches(rows + rows).assign(tourney_level="G"))
    # Second match sees the rating after the first; bigger K -> bigger jump.
    assert boosted.loc[1, "w_elo"] - 1500 == pytest.approx(1.5 * (base.loc[1, "w_elo"] - 1500))
    assert normal.loc[0, "w_elo"] == 1500


def test_layoff_pulls_rating_toward_start():
    rows = [
        ("atp", "t1", "2024-01-01", 1, "F", "Hard", 1, "A", 2, "B"),
        ("atp", "t2", "2024-01-08", 1, "F", "Hard", 1, "A", 3, "C"),
        ("atp", "t3", "2024-09-01", 1, "F", "Hard", 1, "A", 4, "D"),
    ]
    plain = compute_elo(_matches(rows))
    decayed = compute_elo(_matches(rows), EloParams(layoff_days=60, layoff_shrink=0.1))
    # No layoff between match 1 and 2: identical.
    assert decayed.loc[1, "w_elo"] == plain.loc[1, "w_elo"]
    # ~8 month layoff before match 3: A's rating shrinks toward 1500 but stays above it.
    assert 1500 < decayed.loc[2, "w_elo"] < plain.loc[2, "w_elo"]


def test_params_roundtrip(tmp_path):
    p = EloParams(k_scale=300, layoff_shrink=0.05)
    p.save(tmp_path / "p.json")
    assert EloParams.load(tmp_path / "p.json") == p


@pytest.mark.parametrize("odds_name,full_name", [
    ("Djokovic N.", "Novak Djokovic"),
    ("Del Potro J.M.", "Juan Martin del Potro"),
    ("Auger-Aliassime F.", "Felix Auger-Aliassime"),
    ("Carreno Busta P.", "Pablo Carreno Busta"),
    ("Monfils G.", "Gaël Monfils"),
    ("Mpetshi G.", "Giovanni Mpetshi Perricard"),
    ("Zhang Zh.", "Zhizhen Zhang"),
    ("O Connell C.", "Christopher O Connell"),
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


def test_player_index_prefers_full_surname_and_activity():
    from tennis_edge.ingest.results_bridge import player_index

    m = pd.DataFrame({
        "tourney_date": pd.to_datetime(["2024-01-01"] * 3),
        "winner_id": [1, 1, 3], "winner_name": ["Juan Martin", "Juan Martin", "Novak Djokovic"],
        "loser_id": [2, 2, 2], "loser_name": ["Juan Martin del Potro"] * 3,
    })
    idx = player_index(m)
    # 'martin_j' is del Potro's shortened key but Juan Martin's real surname key: real wins.
    assert idx["martin_j"] == ("1", "Juan Martin")
    assert idx["delpotro_j"] == ("2", "Juan Martin del Potro")
    assert idx["djokovic_n"] == ("3", "Novak Djokovic")
