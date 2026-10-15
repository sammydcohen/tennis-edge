"""WTA match odds from the Kaggle dataset "WTA Tennis 2007 - 2026 Daily update" (dissfya).

https://www.kaggle.com/datasets/dissfya/wta-tennis-2007-2023-daily-update

The file carries one bookmaker's odds per match (Odd_1/Odd_2, unlabeled; the ATP sibling
dataset uses Bet365). They are mapped to `oddw`/`oddl` so they never get confused with
the labeled tennis-data.co.uk columns.
"""

import io
import zipfile

import pandas as pd
import requests

from tennis_edge.config import RAW_DIR

URL = "https://www.kaggle.com/api/v1/datasets/download/dissfya/wta-tennis-2007-2023-daily-update"
PATH = RAW_DIR / "kaggle_wta" / "wta.csv"


def download(refresh: bool = False) -> None:
    if PATH.exists() and not refresh:
        return
    resp = requests.get(URL, timeout=120)
    resp.raise_for_status()
    PATH.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        PATH.write_bytes(zf.read("wta.csv"))


def load(years: range, refresh: bool = False) -> pd.DataFrame:
    download(refresh)
    df = pd.read_csv(PATH, low_memory=False)
    df["date"] = pd.to_datetime(df["Date"], errors="coerce")
    for c in ("Odd_1", "Odd_2"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["date", "Winner", "Player_1", "Player_2"])
    df = df[df["date"].dt.year.isin(years)]

    p1_won = df["Winner"] == df["Player_1"]
    return pd.DataFrame({
        "tour": "wta",
        "date": df["date"],
        "tournament": df["Tournament"],
        "winner": df["Winner"],
        "loser": df["Player_2"].where(p1_won, df["Player_1"]),
        "oddw": df["Odd_1"].where(p1_won, df["Odd_2"]),
        "oddl": df["Odd_2"].where(p1_won, df["Odd_1"]),
    }).reset_index(drop=True)
