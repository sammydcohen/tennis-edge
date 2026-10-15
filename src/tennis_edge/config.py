from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
DB_PATH = DATA_DIR / "tennis.duckdb"

SACKMANN_URL = "https://raw.githubusercontent.com/Aneeshers/tennis-sackmann-archive/main/{tour}/{tour}_matches_{year}.csv"
TENNIS_DATA_URL = "http://www.tennis-data.co.uk/{year}/{year}.xlsx"
TENNIS_DATA_WTA_URL = "http://www.tennis-data.co.uk/{year}w/{year}.xlsx"
