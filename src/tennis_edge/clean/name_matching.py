"""Join tennis-data.co.uk odds rows ("Djokovic N.") to Sackmann matches ("Novak Djokovic").

Both names reduce to a key of normalized surname + first initial. Sackmann full names are
ambiguous about where the surname starts ("Juan Martin del Potro"), so every split point
produces a candidate key, and the join is disambiguated by date window and opponent.
"""

import re
import unicodedata

import pandas as pd


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z]", "", s.lower())


def odds_name_key(name: str) -> str:
    """'Del Potro J.M.' -> 'delpotro_j', 'Zhang Zh.' -> 'zhang_z'."""
    name = name.strip()
    m = re.match(r"^(.*?)\s+((?:(?:[A-Za-z]{1,2}\.|[A-Za-z](?=[\s\-]|$))[\s\-]*)+)$", name)
    if not m:
        return _norm(name)
    surname, initials = m.group(1), m.group(2)
    return f"{_norm(surname)}_{_norm(initials)[:1]}"


def full_name_keys(name: str, shortened: bool = True) -> list[str]:
    """'Juan Martin del Potro' -> ['martindelpotro_j', 'delpotro_j', 'potro_j', 'martin_j'].

    The last key (only with `shortened`) covers sources that cut a double surname down to
    its first part ('Mpetshi G.' for Giovanni Mpetshi Perricard).
    """
    tokens = name.replace("-", " ").split()
    if len(tokens) < 2:
        return [_norm(name)]
    initial = _norm(tokens[0])[:1]
    keys = [f"{_norm(''.join(tokens[k:]))}_{initial}" for k in range(1, len(tokens))]
    if shortened and len(tokens) > 2:
        keys.append(f"{_norm(tokens[1])}_{initial}")
    return keys


def _explode_keys(df: pd.DataFrame, col: str, out: str) -> pd.DataFrame:
    keys = df[[col]].drop_duplicates().copy()
    keys[out] = keys[col].map(full_name_keys)
    return keys.explode(out)


def attach_odds(matches: pd.DataFrame, odds: pd.DataFrame, window_days: int = 16) -> pd.DataFrame:
    """Left-join odds columns onto Sackmann matches. Adds an `odds_matched` flag."""
    m = matches.reset_index(names="match_idx")
    o = odds.reset_index(names="odds_idx")
    o["wkey"] = o["winner"].map(odds_name_key)
    o["lkey"] = o["loser"].map(odds_name_key)

    wk = _explode_keys(m, "winner_name", "wkey")
    lk = _explode_keys(m, "loser_name", "lkey")
    cand = (
        m[["match_idx", "tour", "tourney_date", "winner_name", "loser_name"]]
        .merge(wk, on="winner_name")
        .merge(lk, on="loser_name")
        .merge(o[["odds_idx", "tour", "date", "wkey", "lkey"]], on=["tour", "wkey", "lkey"])
    )
    delta = (cand["date"] - cand["tourney_date"]).dt.days
    cand = cand[(delta >= -3) & (delta <= window_days)]
    cand = cand.assign(gap=delta.abs()).sort_values("gap")
    cand = cand.drop_duplicates("match_idx").drop_duplicates("odds_idx")

    odds_cols = ["date", "psw", "psl", "b365w", "b365l", "maxw", "maxl", "avgw", "avgl",
                 "oddw", "oddl", "comment"]
    odds_cols = [c for c in odds_cols if c in o.columns]
    joined = m.merge(
        cand[["match_idx", "odds_idx"]].merge(o[["odds_idx", *odds_cols]], on="odds_idx"),
        on="match_idx",
        how="left",
    )
    joined["odds_matched"] = joined["odds_idx"].notna()
    return joined.drop(columns=["match_idx", "odds_idx"]).rename(columns={"date": "match_date"})
