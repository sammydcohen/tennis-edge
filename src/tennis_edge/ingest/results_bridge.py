"""Extend Sackmann match history up to today using the Kaggle daily-update datasets.

The Sackmann archive stops in mid-2026. The Kaggle ATP and WTA datasets (dissfya) are
refreshed daily, with results, rankings and one bookmaker's odds, but no serve stats or
match durations. Rows from tournaments that start after the last Sackmann tournament are
converted to the Sackmann schema. Players are matched to existing Sackmann ids through the
same surname + initial key used for odds joins; anyone unmatched gets a "K:<key>" id.

Bridged rows leave serve statistics empty, so serve/return ratings stop updating after
the bridge point, while Elo, rankings and form stay current.
"""

import io
import zipfile

import pandas as pd
import requests

from tennis_edge.clean.name_matching import full_name_keys, odds_name_key
from tennis_edge.config import RAW_DIR

SOURCES = {
    "atp": ("https://www.kaggle.com/api/v1/datasets/download/dissfya/atp-tennis-2000-2023daily-pull",
            RAW_DIR / "kaggle_atp" / "atp_tennis.csv"),
    "wta": ("https://www.kaggle.com/api/v1/datasets/download/dissfya/wta-tennis-2007-2023-daily-update",
            RAW_DIR / "kaggle_wta" / "wta.csv"),
}
ROUNDS = {"1st Round": "R128", "2nd Round": "R64", "3rd Round": "R32", "4th Round": "R16",
          "Quarterfinals": "QF", "Semifinals": "SF", "The Final": "F", "Round Robin": "RR",
          "Third Place": "BR"}
ATP_LEVELS = {"Grand Slam": "G", "Masters 1000": "M", "Masters": "M", "Masters Cup": "F"}
SLAMS = ("Australian Open", "French Open", "Roland Garros", "Wimbledon", "US Open")


def download(tour: str, refresh: bool = False) -> pd.DataFrame:
    url, path = SOURCES[tour]
    if refresh or not path.exists():
        resp = requests.get(url, timeout=120)
        resp.raise_for_status()
        path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
            path.write_bytes(zf.read(path.name))
    return pd.read_csv(path, low_memory=False)


def player_index(matches: pd.DataFrame, since_year: int = 2015) -> dict[str, tuple]:
    """Map surname+initial keys to (sackmann id, full name), preferring the most active player."""
    recent = matches[matches["tourney_date"].dt.year >= since_year]
    players = pd.concat([
        recent[["winner_id", "winner_name"]].set_axis(["id", "name"], axis=1),
        recent[["loser_id", "loser_name"]].set_axis(["id", "name"], axis=1),
    ])
    counts = players.value_counts().reset_index(name="n").sort_values("n")
    index = {}
    # Shortened-surname keys first, so a real surname match always overrides them;
    # within each pass the most active player is written last and wins.
    for shortened_pass in (True, False):
        for pid, name, _ in counts.itertuples(index=False):
            keys = set(full_name_keys(name))
            exact = set(full_name_keys(name, shortened=False))
            for key in (keys - exact) if shortened_pass else exact:
                index[key] = (str(pid), name)
    return index


def bridge(tour: str, matches: pd.DataFrame, refresh: bool = False) -> pd.DataFrame:
    """Return Sackmann-schema rows for tournaments after the last one in `matches`."""
    raw = download(tour, refresh)
    raw["date"] = pd.to_datetime(raw["Date"], errors="coerce")
    raw = raw.dropna(subset=["date", "Winner", "Player_1", "Player_2"]).reset_index(drop=True)
    raw["tourney_key"] = raw["Tournament"] + raw["date"].dt.year.astype(str)
    raw["tourney_date"] = raw.groupby("tourney_key")["date"].transform("min")
    raw = raw[raw["tourney_date"] > matches["tourney_date"].max()].reset_index(drop=True)
    if raw.empty:
        return raw

    index = player_index(matches)

    def ident(name: str) -> tuple:
        key = odds_name_key(name)
        return index.get(key, (f"K:{key}", name))

    p1_won = raw["Winner"] == raw["Player_1"]
    loser = raw["Player_2"].where(p1_won, raw["Player_1"])
    winners = raw["Winner"].map(ident)
    losers = loser.map(ident)
    num = lambda c: pd.to_numeric(raw[c], errors="coerce")
    if "Series" in raw:
        level = raw["Series"].map(ATP_LEVELS).fillna("A")
    else:
        level = raw["Tournament"].str.contains("|".join(SLAMS)).map({True: "G", False: "P"})

    out = pd.DataFrame({
        "tourney_id": "K-" + raw["tourney_key"],
        "tourney_name": raw["Tournament"],
        "surface": raw["Surface"],
        "tourney_level": level,
        "tourney_date": raw["tourney_date"],
        "match_num": raw.index,
        "best_of": num("Best of"),
        "round": raw["Round"].map(ROUNDS).fillna("R32"),
        "score": raw["Score"],
        "winner_id": winners.str[0], "winner_name": winners.str[1],
        "loser_id": losers.str[0], "loser_name": losers.str[1],
        "winner_rank": num("Rank_1").where(p1_won, num("Rank_2")),
        "loser_rank": num("Rank_2").where(p1_won, num("Rank_1")),
        "winner_rank_points": num("Pts_1").where(p1_won, num("Pts_2")),
        "loser_rank_points": num("Pts_2").where(p1_won, num("Pts_1")),
        "match_date": raw["date"],
        "oddw": num("Odd_1").where(p1_won, num("Odd_2")),
        "oddl": num("Odd_2").where(p1_won, num("Odd_1")),
        "tour": tour,
        "bridged": True,
    })
    for col in ("winner_rank", "loser_rank", "winner_rank_points", "loser_rank_points"):
        out[col] = out[col].where(out[col] > 0)  # Kaggle uses -1 for unranked
    return out
