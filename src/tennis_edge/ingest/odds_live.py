"""Collect live tennis odds snapshots from The Odds API (https://the-odds-api.com).

Each run stores every bookmaker's current head-to-head price for every upcoming ATP/WTA
match in the DuckDB table `odds_snapshots`. Run it a few times a day: the first snapshot
of an event approximates its opening price and the last one before the start its closing
price, which is what the closing-line-value tracker (betting/clv_tracker.py) compares.

Needs ODDS_API_KEY in the environment or in a `.env` file at the project root.
Each odds request costs (number of regions) credits per active tournament; the free plan
has 500 credits a month, so the default is the "eu" region only (includes Pinnacle).

Usage:  uv run python -m tennis_edge.ingest.odds_live [--regions eu,us]
"""

import argparse
import os

import duckdb
import pandas as pd
import requests

from tennis_edge.config import DB_PATH, ROOT

API = "https://api.the-odds-api.com/v4"


def api_key() -> str:
    key = os.environ.get("ODDS_API_KEY")
    env = ROOT / ".env"
    if not key and env.exists():
        for line in env.read_text().splitlines():
            name, _, value = line.partition("=")
            if name.strip() == "ODDS_API_KEY":
                key = value.strip().strip('"').strip("'")
    if not key:
        raise SystemExit("ODDS_API_KEY not set. Add it to .env at the project root.")
    return key


def _get(path: str, key: str, **params) -> requests.Response:
    """GET from The Odds API without ever exposing the key.

    The API takes the key as a URL parameter, and requests' own exceptions include the
    full URL, so they would print the key into logs and tracebacks. Failures are re-raised
    with only the path and status, and the original exception is suppressed.
    """
    try:
        resp = requests.get(f"{API}{path}", params={"apiKey": key, **params}, timeout=30)
    except requests.RequestException as exc:
        raise RuntimeError(f"Odds API request to {path} failed: {type(exc).__name__}") from None
    if not resp.ok:
        raise RuntimeError(f"Odds API request to {path} failed with HTTP {resp.status_code}")
    return resp


def tennis_sports(key: str) -> list[dict]:
    """Active ATP/WTA singles tournaments. Listing sports does not use any credits."""
    resp = _get("/sports", key)
    return [s for s in resp.json()
            if s["key"].startswith(("tennis_atp", "tennis_wta")) and s.get("active")]


def fetch_odds(key: str, sport: str, regions: str) -> tuple[list[dict], str | None]:
    resp = _get(f"/sports/{sport}/odds", key, regions=regions, markets="h2h", oddsFormat="decimal")
    return resp.json(), resp.headers.get("x-requests-remaining")


def flatten(events: list[dict], sport: dict, fetched_at: pd.Timestamp) -> pd.DataFrame:
    rows = []
    for ev in events:
        for book in ev.get("bookmakers", []):
            for market in book.get("markets", []):
                if market["key"] != "h2h" or len(market["outcomes"]) != 2:
                    continue
                prices = {o["name"]: o["price"] for o in market["outcomes"]}
                rows.append({
                    "fetched_at": fetched_at, "sport_key": sport["key"],
                    "tour": "atp" if sport["key"].startswith("tennis_atp") else "wta",
                    "tournament": sport["title"], "event_id": ev["id"],
                    "commence_time": pd.Timestamp(ev["commence_time"]).tz_localize(None),
                    "player_1": ev["home_team"], "player_2": ev["away_team"],
                    "bookmaker": book["key"],
                    "price_1": prices.get(ev["home_team"]), "price_2": prices.get(ev["away_team"]),
                })
    return pd.DataFrame(rows)


def collect(regions: str = "eu") -> pd.DataFrame:
    key = api_key()
    fetched_at = pd.Timestamp.now(tz="UTC").tz_localize(None)
    frames, remaining = [], None
    for sport in tennis_sports(key):
        events, remaining = fetch_odds(key, sport["key"], regions)
        frames.append(flatten(events, sport, fetched_at))
    snap = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    if not snap.empty:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        with duckdb.connect(str(DB_PATH)) as con:
            con.execute("CREATE TABLE IF NOT EXISTS odds_snapshots AS SELECT * FROM snap LIMIT 0")
            con.execute("INSERT INTO odds_snapshots SELECT * FROM snap")
    print(f"Saved {len(snap):,} prices for {snap['event_id'].nunique() if len(snap) else 0} "
          f"matches. API credits remaining this month: {remaining}")
    return snap


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--regions", default="eu", help="comma-separated, e.g. eu,us,uk")
    collect(ap.parse_args().regions)


if __name__ == "__main__":
    main()
