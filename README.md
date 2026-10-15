# Tennis Edge

Predicts ATP/WTA match outcomes and tests whether those predictions beat the betting market.

- **Ratings:** overall + surface-specific Elo with experience-decayed K-factor (`features/elo.py`)
- **Point model:** serve-point win % → game → tiebreak → set → match Markov chain (`models/markov.py`)
- **Market:** vig removal (proportional & power methods), fractional Kelly, walk-forward backtest with bootstrap ROI confidence intervals (`betting/`)
- **Data:** Sackmann match data joined to tennis-data.co.uk odds via fuzzy name/date matching (`clean/name_matching.py`), stored in DuckDB

## Quickstart

```bash
uv sync
uv run pytest
uv run python -m tennis_edge.pipeline --tour atp --start 2010 --end 2025
```

## Data credits

- Match data: [Jeff Sackmann / Tennis Abstract](https://github.com/JeffSackmann/tennis_atp), CC BY-NC-SA 4.0 — this project is non-commercial.
- Odds: [tennis-data.co.uk](http://www.tennis-data.co.uk/)

For analysis and learning only.
