"""Download historical match odds from tennis-data.co.uk.

Files are .xls up to 2012 and .xlsx from 2013 onward. The site sits behind a Cloudflare
browser check, so automated downloads may be refused; if so, download the yearly files in a
browser and save them as data/raw/tennis_data/{tour}_{year}.xlsx (or .xls). Columns of interest:
PSW/PSL = Pinnacle closing odds, B365W/B365L = Bet365, MaxW/AvgW = market max / average.
"""

from pathlib import Path

import pandas as pd
import requests

from tennis_edge.config import RAW_DIR, TENNIS_DATA_URL, TENNIS_DATA_WTA_URL

KEEP_COLS = [
    "Location", "Tournament", "Date", "Series", "Tier", "Surface", "Round", "Best of",
    "Winner", "Loser", "WRank", "LRank", "Comment",
    "B365W", "B365L", "PSW", "PSL", "MaxW", "MaxL", "AvgW", "AvgL",
]


def _url(tour: str, year: int, ext: str) -> str:
    base = TENNIS_DATA_URL if tour == "atp" else TENNIS_DATA_WTA_URL
    return base.format(year=year).replace(".xlsx", ext)


def download_year(tour: str, year: int, refresh: bool = False) -> Path | None:
    for ext in (".xlsx", ".xls"):
        dest = RAW_DIR / "tennis_data" / f"{tour}_{year}{ext}"
        if dest.exists() and not refresh:
            return dest
        resp = requests.get(_url(tour, year, ext), timeout=60)
        if resp.ok and len(resp.content) > 1000:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(resp.content)
            return dest
    return None


def load(tour: str, years: range, refresh: bool = False) -> pd.DataFrame:
    frames = []
    for year in years:
        path = download_year(tour, year, refresh=refresh)
        if path is None:
            continue
        df = pd.read_excel(path)
        frames.append(df[[c for c in KEEP_COLS if c in df.columns]])
    if not frames:
        return pd.DataFrame()
    odds = pd.concat(frames, ignore_index=True)
    odds["tour"] = tour
    odds["Date"] = pd.to_datetime(odds["Date"], errors="coerce")
    odds = odds.rename(columns={"Best of": "best_of"})
    odds.columns = [c.lower() for c in odds.columns]
    for c in ("b365w", "b365l", "psw", "psl", "maxw", "maxl", "avgw", "avgl"):
        if c in odds:
            odds[c] = pd.to_numeric(odds[c], errors="coerce")  # some files use "-" for missing
    return odds.dropna(subset=["date", "winner", "loser"]).reset_index(drop=True)
