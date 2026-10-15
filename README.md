# Tennis Edge

Predicts ATP/WTA match outcomes and tests whether those predictions beat the betting market.

- **Elo:** overall + surface-specific ratings with experience-decayed K-factor and layoff decay, tuned on held-out data (`features/elo.py`, `models/tune_elo.py`)
- **Serve/return model:** opponent-adjusted serve and return ratings → serve-point win % → game → tiebreak → set → match Markov chain (`features/serve_return.py`, `models/markov.py`)
- **LightGBM:** combines both models with ranking, age, form, fatigue and head-to-head features, trained walk-forward so every prediction uses only earlier data (`features/form.py`, `models/gbm.py`)
- **Market:** vig removal, fractional Kelly, backtests with bootstrap ROI confidence intervals (`betting/`)
- **Data:** Sackmann match data joined to tennis-data.co.uk odds via name/date matching (`clean/name_matching.py`), stored in DuckDB

## Results (ATP, 2020–2025)

All models are evaluated on 2020–2025. Every 2020–2025 prediction comes from a model trained only on earlier years.

### Models vs the market (13,807 matches with Pinnacle odds)

| Model | Log loss | Brier | Accuracy* |
|---|---|---|---|
| Tuned Elo | 0.6239 | 0.2179 | 64.1% |
| Serve/return Markov (calibrated) | 0.6238 | 0.2174 | 64.6% |
| LightGBM (both + form/fatigue/rank) | 0.6082 | 0.2111 | 66.0% |
| **Pinnacle closing odds (margin removed)** | **0.5874** | **0.2022** | — |

\*Accuracy is over all 16,118 test matches.

Elo and the serve/return model reach the same quality from different information. Combining them in LightGBM closes about 40% of the gap to Pinnacle, but the market is still clearly better.

### Betting backtest

The strategy bets whenever the model's probability is more than 3 points above the bookmaker's margin-free probability. The table shows flat-stake ROI with 95% bootstrap confidence intervals:

| Model | vs Pinnacle | vs Bet365 | vs best available price |
|---|---|---|---|
| Elo | −6.4% (−8.7, −3.8) | −9.6% (−11.9, −7.1) | −3.5% (−6.0, −0.9) |
| Serve/return | −2.7% (−5.3, 0.0) | −6.1% (−8.5, −3.6) | +0.2% (−2.4, +2.8) |
| LightGBM | −5.0% (−7.4, −2.7) | −6.6% (−9.0, −4.3) | −2.1% (−4.6, +0.4) |

**No model has a demonstrable edge.** The one break-even result needs the best price across all bookmakers, which isn't realistically available on every bet.

**The bigger the claimed edge, the bigger the loss.** For LightGBM against Pinnacle, bets with a 0–3% edge return +0.5%, while bets with an edge above 15% return −9.8%. Large disagreements with the market usually mean the market knows something the model can't see, such as injuries, withdrawals or motivation.

### WTA (2020–2025, 11,812 matches with odds)

WTA odds come from a Kaggle dataset with a single, unlabeled bookmaker (probably Bet365).

| Model | Log loss | Accuracy | Backtest ROI (edge > 3%) |
|---|---|---|---|
| Tuned Elo | 0.6147 | 64.8% | −7.2% (−9.9, −4.6) |
| Serve/return (calibrated) | 0.6129 | 65.2% | −5.9% (−8.7, −3.2) |
| LightGBM | 0.6037 | 66.6% | −6.4% (−9.0, −3.8) |
| **Bookmaker (margin removed)** | **0.5846** | — | — |

The pattern is the same as ATP: LightGBM is the best model, and the market is still clearly better.

### Searching for a niche edge

An edge might exist only in part of the market, but searching many slices is guaranteed to turn up false winners. To control for that, the search (`eval/segments.py`) splits time:

1. **Discovery, 2020–2022:** every combination of model × bookmaker × condition × edge band is scored. Conditions include tournament level, surface, round, favourite/underdog, odds range, players back from layoffs, inexperienced players, and the fresher player within an event.
2. **Validation, 2023–2025:** only the segments that were profitable in discovery, with at least 150 bets, are scored again on years the search never saw.

| | Count |
|---|---|
| Segments tried (ATP + WTA) | 666 |
| Profitable in discovery | 170 |
| Still profitable in validation | 38 |
| Validation 95% CI entirely above zero | **0** |

The discovered "winners" averaged **−4.1%** in validation, about the same as betting on everything. That's what selection by luck looks like.

**One recurring pattern, tested on unseen 2026 data.** The serve/return model at a 6–10% edge on ATP looked profitable across many slices. It was spotted while exploring the full 2020–2025 data, so the split above isn't a clean test of it. Instead it was stated in advance and tested on January–March 2026, which no model or analysis had used. Pinnacle odds are missing from most of the 2026 file, so the margin-free market average serves as the reference price in both periods:

| Period | Bets | ROI at market average | ROI at Bet365 | ROI at best price |
|---|---|---|---|---|
| 2020–2025 (seen) | 2,726 | +0.6% (−3.7, +5.1) | +1.0% (−3.4, +5.6) | +7.7% (+3.1, +12.8) |
| **2026 Jan–Mar (unseen)** | 151 | **−10.2%** (−29.7, +10.3) | −8.8% (−28.9, +12.7) | −5.3% (−26.5, +16.7) |

It didn't hold up. The only significant number, the best-price ROI, depends on getting the highest odds across all bookmakers, chosen after the fact. That inflates every strategy and isn't reliably available.

### Conclusion

On public data, the ATP and WTA main-tour markets were efficient enough that none of these models found an edge that survived honest testing. The places where an edge is more plausible need data that isn't freely available:
- **Challenger and ITF matches.** Match data exists, but there's no free historical odds source.
- **Opening odds and line movement.** Testing whether the model beats the *closing* price requires timestamped odds.
- **Information the market prices quickly:** injuries, withdrawals, live in-match data.

### Elo tuning

Parameters are fit on 2010–2019 and scored on 2020–2025. Each idea is kept only if it lowers training log loss.

| Stage | Train log loss | Test log loss | Test accuracy |
|---|---|---|---|
| Baseline (FiveThirtyEight constants) | 0.5958 | 0.6333 | 64.0% |
| + tuned surface blend | 0.5958 | 0.6333 | 64.0% |
| + tuned K-factor | 0.5941 | 0.6289 | 63.9% |
| + Grand Slam weighting | 0.5941 | 0.6289 | 63.9% |
| + layoff decay | 0.5932 | **0.6230** | 64.1% |

### Notes

- The raw Markov model is overconfident: it turns small serve-percentage gaps into extreme match probabilities. A logistic calibration fit on training years shrinks it by about 45%.
- In the final LightGBM model, Elo carries about half the predictive gain, the Markov probability about 10%, and surface Elo, rank and age most of the rest.
- Odds were joined to 86.7% of test matches. Nearly all of the rest are team events tennis-data.co.uk doesn't cover (Davis Cup, ATP/United Cup, Olympics, Laver Cup).

## Quickstart

```bash
uv sync
uv run pytest
uv run python -m tennis_edge.models.tune_elo --tour atp   # optional: refit Elo parameters
uv run python -m tennis_edge.pipeline --tour atp           # features, models, evaluation
uv run python -m tennis_edge.pipeline --tour wta           # same for WTA
uv run python -m tennis_edge.eval.segments                 # discovery/validation niche search
uv run streamlit run app/streamlit_app.py                  # dashboard
```

## Data credits

- Match data: [Jeff Sackmann / Tennis Abstract](https://github.com/JeffSackmann/tennis_atp), CC BY-NC-SA 4.0. This project is non-commercial. The original repository is no longer online; the data is downloaded from the archival mirror [Aneeshers/tennis-sackmann-archive](https://github.com/Aneeshers/tennis-sackmann-archive).
- Odds: [tennis-data.co.uk](http://www.tennis-data.co.uk/). The site blocks automated downloads; the 2020–2025 ATP files were taken from the copy in [gmalbert/tennis-predictions](https://github.com/gmalbert/tennis-predictions) and saved to `data/raw/tennis_data/atp_{year}.xlsx`.
- WTA odds: Kaggle dataset [WTA Tennis 2007–2026 Daily update](https://www.kaggle.com/datasets/dissfya/wta-tennis-2007-2023-daily-update), downloaded automatically.

For analysis and learning only.
