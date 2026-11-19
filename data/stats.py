
import pandas as pd
import time
import requests
from pathlib import Path
from nba_api.stats.endpoints import playergamelogs

# -----------------------------
# SETTINGS
# -----------------------------

SEASON = "2026-27"
SEASON_TYPE = "Regular Season"

MAX_RETRIES = 3
REQUEST_TIMEOUT = 120

# Always save next to this file
DATA_DIR = Path(__file__).resolve().parent

BOXSCORES_CSV = DATA_DIR / f"nba_player_boxscores_{SEASON}.csv"
BOXSCORES_PARQUET = DATA_DIR / f"nba_player_boxscores_{SEASON}.parquet"
PLAYERS_CSV = DATA_DIR / "nba_player.csv"

# Temporary export files
TEMP_CSV = DATA_DIR / f"nba_player_boxscores_{SEASON}.tmp.csv"
TEMP_PARQUET = DATA_DIR / f"nba_player_boxscores_{SEASON}.tmp.parquet"
TEMP_PLAYERS = DATA_DIR / "nba_player.tmp.csv"

# -----------------------------
# DATA COLUMNS
# -----------------------------

COLUMNS = [
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

# -----------------------------
# PULL PLAYER GAME LOGS
# -----------------------------

def get_player_game_logs():

    for attempt in range(1, MAX_RETRIES + 1):

        try:
            print(
                f"\nPulling NBA player game logs "
                f"(attempt {attempt}/{MAX_RETRIES})..."
            )

            logs = playergamelogs.PlayerGameLogs(
                season_nullable=SEASON,
                season_type_nullable=SEASON_TYPE,
                timeout=REQUEST_TIMEOUT
            )

            df = logs.get_data_frames()[0]

            if df.empty:
                raise ValueError(
                    "NBA API returned an empty dataset."
                )

            print("NBA API request successful!")

            return df

        except requests.exceptions.RequestException as e:

            print(f"NBA API request failed: {e}")

            if attempt == MAX_RETRIES:
                raise RuntimeError(
                    "Unable to retrieve NBA data after "
                    f"{MAX_RETRIES} attempts."
                ) from e

            wait_time = 30 * attempt

            print(
                f"Waiting {wait_time} seconds before retrying..."
            )

            time.sleep(wait_time)

    raise RuntimeError("NBA data retrieval failed.")

# -----------------------------
# CLEAN DATA
# -----------------------------

def clean_data(df):

    print("\nCleaning NBA data...")

    # Make sure all expected columns exist
    missing_columns = [
        column for column in COLUMNS
        if column not in df.columns
    ]

    if missing_columns:
        raise ValueError(
            f"Missing expected columns: {missing_columns}"
        )

    # Select useful columns
    df = df[COLUMNS].copy()

    # Convert game date to datetime
    df["GAME_DATE"] = pd.to_datetime(
        df["GAME_DATE"],
        errors="coerce"
    )

    # Remove rows without essential information
    df = df.dropna(
        subset=["GAME_DATE", "PLAYER_ID", "PLAYER_NAME", "GAME_ID"]
    )

    if df.empty:
        raise ValueError(
            "No valid player game logs remain after cleaning."
        )

    # Sort by date and player
    df = df.sort_values(
        by=["GAME_DATE", "PLAYER_NAME"]
    )

    return df

# -----------------------------
# EXPORT DATA
# -----------------------------

def export_data(df):

    print("\nPreparing data exports...")

    # Create player list
    players = df["PLAYER_NAME"].dropna().unique()

    players_df = pd.DataFrame(
        players,
        columns=["PLAYER_NAME"]
    )

    players_df = players_df.sort_values(
        "PLAYER_NAME"
    )

    # Write temporary files first
    df.to_csv(
        TEMP_CSV,
        index=False
    )

    df.to_parquet(
        TEMP_PARQUET,
        index=False
    )

    players_df.to_csv(
        TEMP_PLAYERS,
        index=False
    )

    # Replace existing files only after all exports succeed
    TEMP_CSV.replace(BOXSCORES_CSV)
    TEMP_PARQUET.replace(BOXSCORES_PARQUET)
    TEMP_PLAYERS.replace(PLAYERS_CSV)

    print("\nAll files successfully updated!")

# -----------------------------
# MAIN
# -----------------------------

def main():

    try:

        # Pull latest NBA data
        df = get_player_game_logs()

        # Clean data
        df = clean_data(df)

        # Export CSV, Parquet, and player list
        export_data(df)

        # Summary
        print("\nDownload complete!")
        print(f"Total player game logs: {len(df):,}")
        print(f"Unique players: {df['PLAYER_ID'].nunique():,}")
        print(f"Unique games: {df['GAME_ID'].nunique():,}")

        print("\nSample data:")
        print(df.head())

    finally:

        # Remove leftover temporary files
        for file in [
            TEMP_CSV,
            TEMP_PARQUET,
            TEMP_PLAYERS
        ]:
            if file.exists():
                file.unlink()


if __name__ == "__main__":
    main()
