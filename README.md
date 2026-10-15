# Tennis Edge

**Can a model beat the tennis betting market?** This project builds three ATP/WTA match-prediction models, tests them against bookmaker odds as strictly as possible, and runs a live paper-trading system that grades its own picks. A Next.js site (`web/`) presents the findings.

**Short answer: not on public data.** The best model closes about 40% of the gap between a plain rating system and Pinnacle's closing odds, but no betting strategy survives testing on unseen years.

## What's inside

| Layer | What it does | Code |
|---|---|---|
| Data | Sackmann match data since 1990, joined to tennis-data.co.uk / Kaggle odds by name + date matching, kept current with daily result feeds, stored in DuckDB | `ingest/`, `clean/` |
| Elo | Overall + surface ratings, experience-decayed K, layoff decay; tuned on 2010–19, scored on 2020–25 | `features/elo.py`, `models/tune_elo.py` |
| Serve/return | Opponent-adjusted serve and return strengths → point → game → tiebreak → set → match Markov chain, Platt-calibrated | `features/serve_return.py`, `models/markov.py` |
| LightGBM | Both models + rank, age, form, fatigue, head-to-head; trained walk-forward (each year predicted only from earlier years) | `features/form.py`, `models/gbm.py` |
| Market tests | Margin removal, backtests with bootstrap CIs, discovery/validation niche search, closing-line-value tests | `betting/`, `eval/` |
| Live system | Odds snapshots from The Odds API, predictions for upcoming matches, picks logged and graded by closing line value | `ingest/odds_live.py`, `models/predict.py`, `betting/clv_tracker.py` |
| Website | Static Next.js 16 + shadcn/ui + Recharts site built from exported JSON | `export.py`, `web/` |

## Results

### Models vs the market, 2020–2025 (out-of-sample)

| | ATP log loss | ATP accuracy | WTA log loss | WTA accuracy |
|---|---|---|---|---|
| Tuned Elo | 0.6253 | 64.1% | 0.6152 | 64.8% |
| Serve/return (calibrated) | 0.6251 | 64.6% | 0.6133 | 65.2% |
| LightGBM | 0.6094 | 66.0% | 0.6041 | 66.6% |
| **Bookmaker, margin removed** | **0.5888** (Pinnacle) | — | **0.5851** (single book) | — |

ATP: 13,985 matches with Pinnacle odds. WTA: 12,159 matches with odds from one unlabeled bookmaker.

### Betting backtest

Bet whenever the model's probability beats the bookmaker's fair probability by more than 3 points. Flat-stake ROI, with 95% bootstrap CI:

| Model | ATP vs Pinnacle | WTA vs bookmaker |
|---|---|---|
| Elo | −6.3% (−8.6, −3.8) | −7.3% (−9.9, −4.8) |
| Serve/return | −2.5% (−5.1, 0.0) | −5.8% (−8.7, −3.1) |
| LightGBM | −4.9% (−7.3, −2.3) | −6.5% (−9.1, −4.0) |

**The bigger the claimed edge, the bigger the loss.** LightGBM bets with a 0–3% edge roughly break even, while bets with an edge above 15% lose about 10%. Large disagreements with the market usually mean the market knows something the model doesn't (injuries, withdrawals, motivation).

### Unseen data (June–October 2026)

These matches were added after all modelling decisions were made, using the daily result feeds and their bookmaker odds.

| | ATP (940 matches) | WTA (667 matches) |
|---|---|---|
| LightGBM log loss | 0.6202 | 0.6019 |
| Bookmaker log loss | 0.6142 | 0.5677 |
| LightGBM betting ROI | +0.6% (−8.9, +10.3) | −11.3% (−21.7, −0.9) |

### Searching for a niche edge (`eval/segments.py`)

The search scored every model × bookmaker × condition × edge band on 2020–22, then re-tested the profitable slices on 2023–25:

| | Count |
|---|---|
| Slices tested | 666 |
| Profitable in discovery (≥150 bets) | 167 |
| Still profitable in validation | 40 |
| Validation 95% CI above zero | **0** |

Discovered "winners" averaged −3.7% in validation, about the same as betting on everything. A recurring pattern (the serve/return model at 6–10% edge on ATP) was stated in advance and tested on unseen January–March 2026 data, where it lost 10.2% over 151 bets.

### Closing line value (`eval/clv.py`)

This test uses opening and later odds for about 1,700 matches from April to October 2026 (bet365, Kalshi). It asks whether prices move toward the model's picks after it disagrees with the opening line:

| Market | Moved toward model | Moved against | Avg move | ROI at opening odds |
|---|---|---|---|---|
| ATP · Kalshi | 56% | 33% | +1.2 pts | −3.5% |
| ATP · bet365 | 47% | 34% | +0.8 pts | −2.3% |
| WTA · Kalshi | 45% | 37% | +0.7 pts | −8.5% |
| WTA · bet365 | 41% | 33% | +0.5 pts | −10.3% |

Prices do drift toward the model, so it knows a little that opening lines don't. But the drift (~1 point) is far smaller than the bookmaker margin (~5 points). The live tracker repeats this test against Pinnacle going forward.

## Running it

```bash
uv sync && uv run pytest
uv run python -m tennis_edge.models.tune_elo --tour atp      # optional: refit Elo
uv run python -m tennis_edge.pipeline --tour atp --live      # features, models, evaluation (also --tour wta)
uv run python -m tennis_edge.eval.segments                   # niche search
uv run python -m tennis_edge.eval.clv                        # closing-line-value test
uv run python -m tennis_edge.export                          # write site data to web/public/data
cd web && npm install && npm run dev                         # site at localhost:3000
```

### Live paper trading

1. Get a free key at [the-odds-api.com](https://the-odds-api.com) and put `ODDS_API_KEY=...` in `.env` (git-ignored).
2. `scripts/daily_rebuild.ps1` refreshes results and rebuilds models once a day. `scripts/collect_odds.ps1` snapshots odds, predicts upcoming matches, logs picks, grades started ones, and refreshes the site data. Run it a few times a day, for example with Windows Task Scheduler. The free plan (500 credits/month) covers about four snapshots a day with the default `eu` region, which includes Pinnacle.

Live odds outputs (`upcoming.json`, `tracker.json`) stay out of git because The Odds API's terms restrict redistribution.

## Data credits

- Match data: [Jeff Sackmann / Tennis Abstract](https://github.com/JeffSackmann/tennis_atp), CC BY-NC-SA 4.0, via the archival mirror [Aneeshers/tennis-sackmann-archive](https://github.com/Aneeshers/tennis-sackmann-archive). This project is non-commercial.
- Historical odds: [tennis-data.co.uk](http://www.tennis-data.co.uk/). The site blocks automated downloads, so the 2020–2026 ATP files come from the copy in [gmalbert/tennis-predictions](https://github.com/gmalbert/tennis-predictions).
- Daily results and WTA odds: Kaggle [ATP](https://www.kaggle.com/datasets/dissfya/atp-tennis-2000-2023daily-pull) and [WTA](https://www.kaggle.com/datasets/dissfya/wta-tennis-2007-2023-daily-update) daily-update datasets.
- Opening/closing odds, April–October 2026: Flashscore snapshots collected by [gmalbert/tennis-predictions](https://github.com/gmalbert/tennis-predictions).

For analysis and learning only.
