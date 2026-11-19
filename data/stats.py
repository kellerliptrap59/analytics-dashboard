import pandas as pd
import time
from pathlib import Path
from nba_api.stats.endpoints import playergamelogs

# -----------------------------
# SETTINGS
# -----------------------------

SEASON = "2026-27"
SEASON_TYPE = "Regular Season"

# Always save next to this file (the data folder),
# no matter where Streamlit is launched from
DATA_DIR = Path(__file__).resolve().parent

BOXSCORES_CSV = DATA_DIR / f"nba_player_boxscores_{SEASON}.csv"
BOXSCORES_PARQUET = DATA_DIR / f"nba_player_boxscores_{SEASON}.parquet"
PLAYERS_CSV = DATA_DIR / "nba_player.csv"

# -----------------------------
# PULL PLAYER GAME LOGS
# -----------------------------

print(f"Pulling NBA player game logs for {SEASON}...")

logs = playergamelogs.PlayerGameLogs(
    season_nullable=SEASON,
    season_type_nullable=SEASON_TYPE,
    timeout=60
)

df = logs.get_data_frames()[0]

# -----------------------------
# CLEAN DATA
# -----------------------------

# Convert game date to datetime
df["GAME_DATE"] = pd.to_datetime(df["GAME_DATE"])

# Sort by date and player
df = df.sort_values(
    by=["GAME_DATE", "PLAYER_NAME"]
)

# Select useful columns
columns = [
    "GAME_DATE",
    "GAME_ID",
    "PLAYER_ID",
    "PLAYER_NAME",
    "TEAM_ID",
    "TEAM_ABBREVIATION",
    "MATCHUP",
    "WL",
    "MIN",
    "FGM",
    "FGA",
    "FG_PCT",
    "FG3M",
    "FG3A",
    "FG3_PCT",
    "FTM",
    "FTA",
    "FT_PCT",
    "OREB",
    "DREB",
    "REB",
    "AST",
    "STL",
    "BLK",
    "TOV",
    "PF",
    "PTS",
    "PLUS_MINUS",
    "NBA_FANTASY_PTS",
    "DD2",
    "TD3"
]

df = df[columns]

# -----------------------------
# EXPORT DATA
# -----------------------------

df.to_csv(
    BOXSCORES_CSV,
    index=False
)

df.to_parquet(
    BOXSCORES_PARQUET,
    index=False
)

# -----------------------------
# SUMMARY
# -----------------------------

print("\nDownload complete!")
print(f"Total player game logs: {len(df):,}")
print(f"Unique players: {df['PLAYER_ID'].nunique():,}")
print(f"Unique games: {df['GAME_ID'].nunique():,}")

print("\nSample data:")
print(df.head())

# -----------------------------
# PLAYER LIST
# -----------------------------

df = pd.read_csv(BOXSCORES_CSV)

players = df["PLAYER_NAME"].dropna().unique()

players_df = pd.DataFrame(players, columns=["PLAYER_NAME"])

players_df = players_df.sort_values("PLAYER_NAME")

players_df.to_csv(PLAYERS_CSV, index=False)