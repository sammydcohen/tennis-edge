import pytest

from tennis_edge.models.markov import p_game, p_match, p_set, p_tiebreak


def test_game_known_value():
    # Standard textbook value: 60% on serve -> ~73.6% hold.
    assert p_game(0.6) == pytest.approx(0.7357, abs=1e-4)


@pytest.mark.parametrize("p", [0.0, 0.5, 1.0])
def test_game_edges(p):
    assert p_game(p) == pytest.approx(p)


def test_equal_players_are_coin_flips():
    for p in (0.55, 0.62, 0.7):
        assert p_tiebreak(p, p) == pytest.approx(0.5)
        assert p_set(p, p) == pytest.approx(0.5)
        assert p_match(p, p, 3) == pytest.approx(0.5)
        assert p_match(p, p, 5) == pytest.approx(0.5)


def test_symmetry_and_monotonic():
    a, b = 0.66, 0.62
    assert p_match(a, b) + p_match(b, a) == pytest.approx(1.0)
    assert p_match(a, b) > 0.5
    # Best-of-5 amplifies the better player's edge.
    assert p_match(a, b, 5) > p_match(a, b, 3)
