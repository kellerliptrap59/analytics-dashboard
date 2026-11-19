import pandas as pd
import streamlit as st
import sqlite3
import subprocess
import sys
import altair as alt

# ---- Page setup (visual) ----
st.set_page_config(page_title="NBA Analytics Dashboard", page_icon="🏀", layout="wide")

st.title("🏀 NBA Analytics Dashboard")
st.caption("See how often a player has cleared a stat line over their recent games.")

# Automatically update NBA data once per session
if "data_updated" not in st.session_state:
    with st.spinner("Updating NBA game data..."):
        try:
            subprocess.run(
                [sys.executable, "data/stats.py"],
                check=True,
                capture_output=True,
                text=True, 
                timeout=120
            )
            st.toast("NBA data successfully updated!", icon="✅")

        except subprocess.TimeoutExpired:
            st.warning("The NBA data update timed out. Showing the last saved data.")

        except subprocess.CalledProcessError as e:
            st.warning("Unable to update NBA data. Showing the last saved data.")
            with st.expander("Error details"):
                st.code(e.stderr)

    st.session_state.data_updated = True

# Connect to database
conn = sqlite3.connect("data/nba.db")

df = pd.read_csv("data/nba_player_boxscores_2026-27.csv")

df.to_sql("player_game_logs", conn, if_exists="replace", index=False)

stat_options = {
    "3-Pointers Made": "FG3M",
    "Offensive Rebounds": "OREB",
    "Defensive Rebounds": "DREB",
    "Total Rebounds": "REB",
    "Assists": "AST",
    "Steals": "STL",
    "Blocks": "BLK",
    "Turnovers": "TOV",
    "Personal Fouls": "PF",
    "Points": "PTS"
}

left_col, right_col = st.columns([1, 2], gap="large")

# LEFT COLUMN:
with left_col:
    with st.container(border=True):
        st.subheader("Player & Prop Selection")

        selected_player = st.selectbox(
            "Select a Player",
            pd.read_csv("data/nba_player.csv")["PLAYER_NAME"].tolist()
        )

        selected_stat = st.selectbox(
            "Select a Statistic",
            list(stat_options.keys())
        )

        selected_side = st.radio(
            "Select Over or Under",
            ["Over", "Under"],
            horizontal=True
        )

        betting_line = st.number_input(
            "Stat Line",
            min_value=0.0,
            value=0.0,
            step=0.5
        )

        games_available = int((df["PLAYER_NAME"] == selected_player).sum())
        max_games = max(games_available, 1)

        number_of_games = st.number_input(
        f"Number of Games to Analyze (max {games_available})",
        min_value=1,
        max_value=max_games,
        value=min(10, max_games),
        step=1
)

# Get SQL column name for selected statistic
stat = stat_options[selected_stat]

# SQL query
query = f"""
SELECT
    PLAYER_NAME,
    GAME_DATE,
    CASE
        WHEN MATCHUP LIKE '% vs. %'
            THEN TRIM(REPLACE(MATCHUP, TEAM_ABBREVIATION || ' vs.', ''))
        WHEN MATCHUP LIKE '% @ %'
            THEN TRIM(REPLACE(MATCHUP, TEAM_ABBREVIATION || ' @', ''))
    END AS OPPONENT,
    CASE
        WHEN MATCHUP LIKE '% vs. %' THEN 'HOME'
        ELSE 'AWAY'
    END AS LOCATION,
    {stat}
FROM player_game_logs
WHERE PLAYER_NAME = ?
ORDER BY GAME_DATE DESC
LIMIT ?
"""

results = pd.read_sql_query(
    query,
    conn,
    params=(selected_player, number_of_games)
)

conn.close()

if selected_side == "Over":
    hits = (results[stat] > betting_line).sum()
else:
    hits = (results[stat] < betting_line).sum()

total_games = len(results)

hit_rate = (
    (hits / total_games) * 100
    if total_games > 0
    else 0
)

# RIGHT COLUMN:
with right_col:
    st.subheader(
        f"{selected_player}: {selected_side} {betting_line:g} {selected_stat}"
    )

    if total_games > 0:
        average = results[stat].mean()

        m1, m2, m3 = st.columns(3)

        m1.metric(f"{selected_side} Rate", f"{hit_rate:.1f}%")
        m2.metric("Record", f"{hits} of {total_games} games")
        m3.metric(
            f"Average {selected_stat}",
            f"{average:.1f}",
            delta=f"{average - betting_line:+.1f} vs line",
            delta_color="normal" if selected_side == "Over" else "inverse"
        )

        # Chart: green = hit, red = miss, dashed line = your stat line
        chart_df = results.copy()

        if selected_side == "Over":
            chart_df["Result"] = (chart_df[stat] > betting_line).map({True: "Hit", False: "Miss"})
        else:
            chart_df["Result"] = (chart_df[stat] < betting_line).map({True: "Hit", False: "Miss"})

        chart_df = chart_df.iloc[::-1]  # oldest to newest, left to right
        chart_df["Game"] = chart_df["GAME_DATE"].astype(str) + " " + chart_df["OPPONENT"].astype(str)

        bars = (
            alt.Chart(chart_df)
            .mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3)
            .encode(
                x=alt.X("Game:N", sort=chart_df["Game"].tolist(), title=None,
                        axis=alt.Axis(labelAngle=-45)),
                y=alt.Y(f"{stat}:Q", title=selected_stat),
                color=alt.Color(
                    "Result:N",
                    scale=alt.Scale(domain=["Hit", "Miss"], range=["#2E7D5B", "#C4503C"]),
                    legend=alt.Legend(title=None, orient="top")
                ),
                tooltip=["GAME_DATE", "OPPONENT", "LOCATION", stat, "Result"]
            )
        )

        line = (
            alt.Chart(pd.DataFrame({"line": [betting_line]}))
            .mark_rule(strokeDash=[6, 4], color="gray", size=2)
            .encode(y="line:Q")
        )

        st.altair_chart((bars + line).properties(height=300), use_container_width=True)
    else:
        st.info("No games found.")

    st.subheader("Game Statistics")
    st.dataframe(results, use_container_width=True, hide_index=True)

