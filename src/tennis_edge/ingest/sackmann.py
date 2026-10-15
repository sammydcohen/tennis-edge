"""Download Jeff Sackmann's ATP/WTA match CSVs (CC BY-NC-SA 4.0).

Source: https://github.com/JeffSackmann/tennis_atp and tennis_wta
"""

from pathlib import Path

import pandas as pd
import requests

from tennis_edge.config import RAW_DIR, SACKMANN_URL

KEEP_COLS = [
    "tourney_id", "tourney_name", "surface", "tourney_level", "tourney_date", "match_num",
    "best_of", "round", "minutes", "score",
    "winner_id", "winner_name", "winner_rank", "winner_rank_points", "winner_age", "winner_hand",
    "loser_id", "loser_name", "loser_rank", "loser_rank_points", "loser_age", "loser_hand",
    "w_ace", "w_df", "w_svpt", "w_1stIn", "w_1stWon", "w_2ndWon", "w_SvGms", "w_bpSaved", "w_bpFaced",
    "l_ace", "l_df", "l_svpt", "l_1stIn", "l_1stWon", "l_2ndWon", "l_SvGms", "l_bpSaved", "l_bpFaced",
]


def download_year(tour: str, year: int, refresh: bool = False) -> Path | None:
    dest = RAW_DIR / "sackmann" / f"{tour}_matches_{year}.csv"
    if dest.exists() and not refresh:
        return dest
    resp = requests.get(SACKMANN_URL.format(tour=tour, year=year), timeout=60)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(resp.content)
    return dest


def load(tour: str, years: range, refresh: bool = False) -> pd.DataFrame:
    frames = []
    for year in years:
        path = download_year(tour, year, refresh=refresh)
        if path is None:
            continue
        df = pd.read_csv(path, low_memory=False)
        frames.append(df[[c for c in KEEP_COLS if c in df.columns]])
    matches = pd.concat(frames, ignore_index=True)
    matches["tour"] = tour
    matches["tourney_date"] = pd.to_datetime(matches["tourney_date"].astype(str), format="%Y%m%d")
    return matches.sort_values(["tourney_date", "tourney_id", "match_num"]).reset_index(drop=True)
