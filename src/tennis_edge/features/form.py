"""Pre-match form, fatigue, experience and head-to-head features.

Sackmann rows only carry the tournament start date, not the match date, so fatigue is
measured two ways: work done earlier in the *same* tournament (matches and minutes), and
matches played in tournaments that started in the previous 14 days.

`matches` must already be in chronological order (see features.elo.sort_matches).
"""

from collections import defaultdict, deque

import numpy as np
import pandas as pd

FORM_ALPHA = 0.1  # weight of the latest result in the exponentially weighted win rate


def compute_form(matches: pd.DataFrame) -> pd.DataFrame:
    n = len(matches)
    names = ["days_off", "recent_14d", "tourn_matches", "tourn_minutes", "form", "career", "h2h"]
    cols = {f"{side}_{k}": np.full(n, np.nan) for side in ("w", "l") for k in names}

    last_day: dict = {}
    recent: dict = defaultdict(deque)  # player -> tourney start days of recent matches
    tourn: dict = defaultdict(lambda: [0, 0.0])  # (player, tourney_id) -> [matches, minutes]
    form: dict = defaultdict(lambda: 0.5)
    career: dict = defaultdict(int)
    h2h: dict = defaultdict(int)  # (a, b) -> wins of a over b

    w_ids = matches["winner_id"].to_numpy()
    l_ids = matches["loser_id"].to_numpy()
    t_ids = matches["tourney_id"].to_numpy()
    days = matches["tourney_date"].to_numpy().astype("datetime64[D]").astype(np.int64)
    minutes = matches["minutes"].fillna(0).to_numpy(dtype=float)

    for i in range(n):
        w, l, t, d = w_ids[i], l_ids[i], t_ids[i], days[i]
        for side, me, opp in (("w", w, l), ("l", l, w)):
            q = recent[me]
            while q and d - q[0] > 14:
                q.popleft()
            cols[f"{side}_days_off"][i] = d - last_day[me] if me in last_day else np.nan
            cols[f"{side}_recent_14d"][i] = sum(1 for x in q if x < d)  # earlier events only
            cols[f"{side}_tourn_matches"][i], cols[f"{side}_tourn_minutes"][i] = tourn[(me, t)]
            cols[f"{side}_form"][i] = form[me]
            cols[f"{side}_career"][i] = career[me]
            cols[f"{side}_h2h"][i] = h2h[(me, opp)]

        for me, won in ((w, 1.0), (l, 0.0)):
            last_day[me] = d
            recent[me].append(d)
            tourn[(me, t)][0] += 1
            tourn[(me, t)][1] += minutes[i]
            form[me] += FORM_ALPHA * (won - form[me])
            career[me] += 1
        h2h[(w, l)] += 1

    return matches.assign(**cols)
