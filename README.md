# Tennis Edge

Predicts ATP/WTA match outcomes and tests whether those predictions beat the betting market.

- **Ratings:** overall + surface-specific Elo with experience-decayed K-factor (`features/elo.py`)
- **Point model:** serve-point win % → game → tiebreak → set → match Markov chain (`models/markov.py`)
- **Market:** vig removal (proportional & power methods), fractional Kelly, walk-forward backtest with bootstrap ROI confidence intervals (`betting/`)
- **Data:** Sackmann match data joined to tennis-data.co.uk odds via fuzzy name/date matching (`clean/name_matching.py`), stored in DuckDB

## Results so far (ATP)

### Elo tuning

Parameters are fit on 2010–2019 and evaluated on held-out 2020–2025 matches (ratings run from 1990 so they can settle). Each idea is kept only if it lowers training log loss.

| Stage | Train log loss | Test log loss | Test accuracy |
|---|---|---|---|
| Baseline (FiveThirtyEight constants) | 0.5958 | 0.6333 | 64.0% |
| + tuned surface blend | 0.5958 | 0.6333 | 64.0% |
| + tuned K-factor | 0.5941 | 0.6289 | 63.9% |
| + Grand Slam weighting | 0.5941 | 0.6289 | 63.9% |
| + layoff decay | 0.5932 | **0.6230** | 64.1% |

The 50/50 surface blend and equal Slam weighting were already optimal. Pulling ratings toward average after layoffs gave the biggest gain.

### Elo vs the market (2020–2025, 13,807 matches with Pinnacle odds)

| | Log loss | Brier |
|---|---|---|
| Tuned Elo | 0.6239 | 0.2179 |
| Pinnacle closing odds (margin removed) | **0.5874** | **0.2022** |

Betting every match where Elo's edge over the fair price is above 3%:

| Bookmaker | Bets | Flat-stake ROI | 95% CI |
|---|---|---|---|
| Pinnacle | 8,800 | −6.4% | −8.7% to −3.8% |
| Bet365 | 9,287 | −9.6% | −11.9% to −7.1% |
| Best available price | 8,793 | −3.5% | −6.0% to −0.9% |

**Elo alone has no edge.** The market's probabilities are much better, and the "value bets" Elo finds are mostly cases where the market knows something Elo doesn't. This is the baseline the Markov and ML models need to close.

Odds were matched to 86.7% of matches; nearly all of the rest are team events tennis-data.co.uk doesn't cover (Davis Cup, ATP/United Cup, Olympics, Laver Cup).

## Quickstart

```bash
uv sync
uv run pytest
uv run python -m tennis_edge.pipeline --tour atp --start 2010 --end 2025
```

## Data credits

- Match data: [Jeff Sackmann / Tennis Abstract](https://github.com/JeffSackmann/tennis_atp), CC BY-NC-SA 4.0 — this project is non-commercial.
- Odds: [tennis-data.co.uk](http://www.tennis-data.co.uk/). The site blocks automated downloads; the 2020–2025 ATP files were taken from the copy in [gmalbert/tennis-predictions](https://github.com/gmalbert/tennis-predictions) and saved to `data/raw/tennis_data/atp_{year}.xlsx`.

For analysis and learning only.
