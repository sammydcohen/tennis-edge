"""Tennis Edge dashboard.  Run:  uv run streamlit run app/streamlit_app.py"""

import duckdb
import pandas as pd
import streamlit as st

from tennis_edge.config import DB_PATH
from tennis_edge.eval.metrics import accuracy, calibration_table, log_loss, symmetric

st.set_page_config(page_title="Tennis Edge", layout="wide")


@st.cache_data
def load(tour: str) -> pd.DataFrame:
    with duckdb.connect(str(DB_PATH), read_only=True) as con:
        return con.execute(f"SELECT * FROM {tour}_matches").df()


@st.cache_data
def player_history(df: pd.DataFrame) -> pd.DataFrame:
    cols = ["tourney_date", "tourney_name", "surface", "round"]
    w = df[cols + ["winner_name", "w_elo", "w_selo", "loser_name"]].rename(
        columns={"winner_name": "player", "w_elo": "elo", "w_selo": "surface_elo", "loser_name": "opponent"})
    l = df[cols + ["loser_name", "l_elo", "l_selo", "winner_name"]].rename(
        columns={"loser_name": "player", "l_elo": "elo", "l_selo": "surface_elo", "winner_name": "opponent"})
    return pd.concat([w.assign(result="W"), l.assign(result="L")]).sort_values("tourney_date")


st.title("🎾 Tennis Edge")
tour = st.sidebar.selectbox("Tour", ["atp"])
df = load(tour)
hist = player_history(df)
st.caption(f"{len(df):,} matches · {df['tourney_date'].min():%Y} – {df['tourney_date'].max():%Y} · "
           "pre-match Elo ratings (no lookahead)")

tab_rank, tab_player, tab_model = st.tabs(["Elo rankings", "Player", "Model accuracy"])

with tab_rank:
    cutoff = df["tourney_date"].max() - pd.Timedelta(days=365)
    recent = hist[hist["tourney_date"] >= cutoff]
    latest = recent.groupby("player").last()
    latest = latest[recent.groupby("player").size() >= 10]
    surface = st.radio("Rating", ["Overall", "Hard", "Clay", "Grass"], horizontal=True)
    if surface == "Overall":
        board = latest["elo"]
    else:
        s = recent[recent["surface"] == surface].groupby("player")["surface_elo"].last()
        board = s[s.index.isin(latest.index)]
    board = board.sort_values(ascending=False).head(25).round(0).astype(int)
    st.dataframe(board.rename("Elo").reset_index().rename_axis("Rank").rename(index=lambda i: i + 1),
                 use_container_width=True, height=600)

with tab_player:
    players = sorted(hist["player"].unique())
    default = players.index("Jannik Sinner") if "Jannik Sinner" in players else 0
    name = st.selectbox("Player", players, index=default)
    ph = hist[hist["player"] == name]
    c1, c2, c3 = st.columns(3)
    c1.metric("Matches", len(ph))
    c2.metric("Win rate", f"{(ph['result'] == 'W').mean():.1%}")
    c3.metric("Peak Elo", f"{ph['elo'].max():.0f}")
    st.line_chart(ph.set_index("tourney_date")[["elo"]])
    st.dataframe(ph.tail(15).iloc[::-1], use_container_width=True, hide_index=True)

with tab_model:
    rated = df.dropna(subset=["p_elo_winner"])
    p, y = symmetric(rated["p_elo_winner"])
    c1, c2, c3 = st.columns(3)
    c1.metric("Accuracy", f"{accuracy(p, y):.1%}")
    c2.metric("Log loss", f"{log_loss(p, y):.4f}")
    c3.metric("Bookmaker comparison", "needs odds data")
    yearly = rated.groupby(rated["tourney_date"].dt.year).apply(
        lambda g: accuracy(*symmetric(g["p_elo_winner"])), include_groups=False)
    st.subheader("Accuracy by year")
    st.bar_chart(yearly.rename("accuracy"))
    st.subheader("Calibration: predicted vs actual win rate")
    cal = calibration_table(p, y)
    st.line_chart(cal.assign(perfect=cal["mean_pred"]).set_index("mean_pred")[["observed", "perfect"]])
