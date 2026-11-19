import sys
from pathlib import Path

import pandas as pd
import streamlit as st
import sqlite3
import altair as alt

# ---- Page setup ----
st.set_page_config(
    page_title="NBA Analytics Dashboard",
    page_icon="🏀",
    layout="wide"
)

st.title("🏀 NBA Analytics Dashboard")
st.caption("Analyze player performance and see how often they clear a selected stat line.")

# ---- Load NBA data (auto-updates when the app loads) ----
sys.path.append(str(Path(__file__).resolve().parent / "data"))
import stats


@st.cache_data(ttl=3 * 60 * 60, show_spinner="Checking for new NBA games...")
def load_data():
    try:
        df = stats.update_data()
        try:
            stats.export_data(df)   # best effort; helps until the app restarts
        except Exception as e:
            print(f"Could not save files: {e}")
    except Exception as e:
        print(f"Update failed, using existing CSV: {e}")
        df = stats.clean_data(pd.read_csv(stats.BOXSCORES_CSV))

    # Keep dates as plain strings, like they were when read from the CSV
    df["GAME_DATE"] = df["GAME_DATE"].dt.strftime("%Y-%m-%d")
    return df


df = load_data()

st.caption(f"Data through {df['GAME_DATE'].max()}")

conn = sqlite3.connect(":memory:")
df.to_sql(
    "player_game_logs",
    conn,
    if_exists="replace",
    index=False
)

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

# ---- LEFT COLUMN ----
with left_col:
    with st.container(border=True):

        st.subheader("Player & Prop Selection")

        players = sorted(
            df["PLAYER_NAME"].dropna().unique().tolist()
        )

        selected_player = st.selectbox(
            "Select a Player",
            players
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

        games_available = int(
            (df["PLAYER_NAME"] == selected_player).sum()
        )

        max_games = max(games_available, 1)

        number_of_games = st.number_input(
            f"Number of Games to Analyze (max {games_available})",
            min_value=1,
            max_value=max_games,
            value=min(10, max_games),
            step=1
        )

# ---- SQL QUERY ----

stat = stat_options[selected_stat]

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
    params=(selected_player, int(number_of_games))
)

conn.close()


total_games = len(results)

if selected_side == "Over":
    overs = (results[stat] > betting_line).sum()
else:
    overs = (results[stat] < betting_line).sum()

unders = total_games - overs

result_rate = (
    (overs / total_games) * 100
    if selected_side == "Over" and total_games > 0
    else (unders / total_games) * 100
    if total_games > 0
    else 0
)

# ---- RIGHT COLUMN ----
with right_col:

    st.subheader(
        f"{selected_player}: {selected_side} {betting_line:g} {selected_stat}"
    )

    if total_games > 0:

        average = results[stat].mean()

        st.subheader(
            f"{selected_player} has averaged {average:.2f} "
            f"{selected_stat.lower()} per game over their last "
            f"{total_games} games."
        )

        m1, m2, m3 = st.columns(3)

        m1.metric(
            f"{selected_side} Rate",
            f"{result_rate:.1f}%"
        )

        m2.metric(
            f"Average {selected_stat}",
            f"{average:.1f}",
            delta=f"{average - betting_line:+.1f} vs line",
            delta_color="normal" if selected_side == "Over" else "inverse"
        )

        chart_df = results.copy()

        chart_df["Result"] = (
            chart_df[stat] > betting_line
        ).map({
            True: "Over",
            False: "Under"
        })

        chart_df = chart_df.iloc[::-1]

        chart_df["Game"] = (
            chart_df["GAME_DATE"].astype(str)
            + " "
            + chart_df["OPPONENT"].astype(str)
        )

        bars = (
            alt.Chart(chart_df)
            .mark_bar(
                cornerRadiusTopLeft=3,
                cornerRadiusTopRight=3
            )
            .encode(
                x=alt.X(
                    "Game:N",
                    sort=chart_df["Game"].tolist(),
                    title=None,
                    axis=alt.Axis(labelAngle=-45)
                ),
                y=alt.Y(
                    f"{stat}:Q",
                    title=selected_stat
                ),
                color=alt.Color(
                    "Result:N",
                    scale=alt.Scale(
                        domain=["Over", "Under"],
                        range=["#2E7D5B", "#C4503C"]
                    ),
                    legend=alt.Legend(
                        title=None,
                        orient="top"
                    )
                ),
                tooltip=[
                    "GAME_DATE",
                    "OPPONENT",
                    "LOCATION",
                    stat,
                    "Result"
                ]
            )
        )

        line = (
            alt.Chart(
                pd.DataFrame({"line": [betting_line]})
            )
            .mark_rule(
                strokeDash=[6, 4],
                color="gray",
                size=2
            )
            .encode(
                y="line:Q"
            )
        )

        st.altair_chart(
            (bars + line).properties(height=300),
            use_container_width=True
        )

    else:
        st.info("No games found for this player.")

    st.subheader("Game Statistics")

    st.dataframe(
        results,
        use_container_width=True,
        hide_index=True
    )

# st.download_button(
#     "Download latest data (CSV)",
#     df.to_csv(index=False),
#     file_name=f"nba_player_boxscores_{stats.SEASON}.csv",
# )