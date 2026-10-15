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
uv run streamlit run app/streamlit_app.py                  # dashboard
```

## Data credits

- Match data: [Jeff Sackmann / Tennis Abstract](https://github.com/JeffSackmann/tennis_atp), CC BY-NC-SA 4.0. This project is non-commercial. The original repository is no longer online; the data is downloaded from the archival mirror [Aneeshers/tennis-sackmann-archive](https://github.com/Aneeshers/tennis-sackmann-archive).
- Odds: [tennis-data.co.uk](http://www.tennis-data.co.uk/). The site blocks automated downloads; the 2020–2025 ATP files were taken from the copy in [gmalbert/tennis-predictions](https://github.com/gmalbert/tennis-predictions) and saved to `data/raw/tennis_data/atp_{year}.xlsx`.

For analysis and learning only.
