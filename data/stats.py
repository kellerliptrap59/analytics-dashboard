
import pandas as pd
import time
import requests

from datetime import datetime, timedelta
from pathlib import Path
from nba_api.stats.endpoints import playergamelogs

# -----------------------------
# SETTINGS
# -----------------------------

SEASON = "2026-27"
SEASON_TYPE = "Regular Season"

MAX_RETRIES = 3
REQUEST_TIMEOUT = 120
LOOKBACK_DAYS = 3

DATA_DIR = Path(__file__).resolve().parent

BOXSCORES_CSV = DATA_DIR / f"nba_player_boxscores_{SEASON}.csv"
BOXSCORES_PARQUET = DATA_DIR / f"nba_player_boxscores_{SEASON}.parquet"
PLAYERS_CSV = DATA_DIR / "nba_player.csv"

TEMP_CSV = DATA_DIR / f"nba_player_boxscores_{SEASON}.tmp.csv"
TEMP_PARQUET = DATA_DIR / f"nba_player_boxscores_{SEASON}.tmp.parquet"
TEMP_PLAYERS = DATA_DIR / "nba_player.tmp.csv"

COLUMNS = [
    "GAME_DATE", "GAME_ID", "PLAYER_ID", "PLAYER_NAME", "TEAM_ID",
    "TEAM_ABBREVIATION", "MATCHUP", "WL", "MIN", "FGM", "FGA",
    "FG_PCT", "FG3M", "FG3A", "FG3_PCT", "FTM", "FTA", "FT_PCT",
    "OREB", "DREB", "REB", "AST", "STL", "BLK", "TOV", "PF", "PTS",
    "PLUS_MINUS", "NBA_FANTASY_PTS", "DD2", "TD3"
]


# -----------------------------
# DOWNLOAD NEW DATA
# -----------------------------

def get_player_game_logs(start_date, end_date):

    for attempt in range(1, MAX_RETRIES + 1):

        try:
            print(
                f"Downloading games from {start_date} "
                f"through {end_date}..."
            )

            logs = playergamelogs.PlayerGameLogs(
                season_nullable=SEASON,
                season_type_nullable=SEASON_TYPE,
                date_from_nullable=start_date.strftime("%m/%d/%Y"),
                date_to_nullable=end_date.strftime("%m/%d/%Y"),
                timeout=REQUEST_TIMEOUT
            )

            df = logs.get_data_frames()[0]

            print(f"Retrieved {len(df):,} player game logs.")

            return df

        except requests.exceptions.RequestException as e:

            print(f"Request failed: {e}")

            if attempt == MAX_RETRIES:
                raise RuntimeError(
                    "Unable to retrieve NBA data after "
                    f"{MAX_RETRIES} attempts."
                ) from e

            wait_time = 30 * attempt

            print(f"Retrying in {wait_time} seconds...")
            time.sleep(wait_time)

    raise RuntimeError("NBA data retrieval failed.")


# -----------------------------
# CLEAN DATA
# -----------------------------

def clean_data(df):

    print("\nCleaning NBA data...")

    missing_columns = [
        column for column in COLUMNS
        if column not in df.columns
    ]

    if missing_columns:
        raise ValueError(
            f"Missing expected columns: {missing_columns}"
        )

    df = df[COLUMNS].copy()

    # Convert dates
    df["GAME_DATE"] = pd.to_datetime(
        df["GAME_DATE"],
        errors="coerce"
    )

    # Keep IDs as strings to preserve leading zeros
    df["GAME_ID"] = (
        df["GAME_ID"].astype("string").str.zfill(10)
    )

    df["PLAYER_ID"] = (
        df["PLAYER_ID"].astype("string").str.zfill(7)
    )

    df["TEAM_ID"] = (
        df["TEAM_ID"].astype("string").str.zfill(10)
    )

    # Remove invalid records
    df = df.dropna(
        subset=[
            "GAME_DATE",
            "PLAYER_ID",
            "PLAYER_NAME",
            "GAME_ID"
        ]
    )

    return df


# -----------------------------
# INCREMENTAL UPDATE
# -----------------------------

def update_data():

    if not BOXSCORES_CSV.exists():
        raise FileNotFoundError(
            f"Existing CSV not found: {BOXSCORES_CSV}. "
            "Run a full-season download first."
        )

    print("Reading existing NBA data...")

    existing_df = pd.read_csv(BOXSCORES_CSV)

    existing_df = clean_data(existing_df)

    latest_date = existing_df["GAME_DATE"].max().date()

    # Recheck the last three days to catch late updates.
    start_date = latest_date - timedelta(days=LOOKBACK_DAYS)

    end_date = datetime.today().date()

    print(f"Latest date already stored: {latest_date}")
    print(f"Checking for updates from: {start_date}")

    if start_date > end_date:
        print("No new dates to check.")
        return existing_df

    new_df = get_player_game_logs(start_date, end_date)

    if new_df.empty:
        print("No new games returned by the NBA API.")
        return existing_df

    new_df = clean_data(new_df)

    # Combine old and newly downloaded data.
    combined_df = pd.concat(
        [existing_df, new_df],
        ignore_index=True
    )

    # Remove duplicate player-game records.
    combined_df = combined_df.drop_duplicates(
        subset=["GAME_ID", "PLAYER_ID"],
        keep="last"
    )

    combined_df = combined_df.sort_values(
        by=["GAME_DATE", "PLAYER_NAME"]
    )

    print(f"Previous records: {len(existing_df):,}")
    print(f"Downloaded records: {len(new_df):,}")
    print(f"Updated records: {len(combined_df):,}")

    return combined_df


# -----------------------------
# EXPORT UPDATED FILES
# -----------------------------

def export_data(df):

    print("\nExporting updated files...")

    players_df = (
        df[["PLAYER_NAME"]]
        .drop_duplicates()
        .sort_values("PLAYER_NAME")
    )

    # Write temporary files first.
    df.to_csv(TEMP_CSV, index=False)
    df.to_parquet(TEMP_PARQUET, index=False)
    players_df.to_csv(TEMP_PLAYERS, index=False)

    # Replace the existing files.
    TEMP_CSV.replace(BOXSCORES_CSV)
    TEMP_PARQUET.replace(BOXSCORES_PARQUET)
    TEMP_PLAYERS.replace(PLAYERS_CSV)

    print("All files successfully updated!")


# -----------------------------
# MAIN
# -----------------------------

def main():

    try:
        df = update_data()

        export_data(df)

        print("\nUpdate complete!")
        print(f"Total player game logs: {len(df):,}")
        print(f"Unique players: {df['PLAYER_ID'].nunique():,}")
        print(f"Unique games: {df['GAME_ID'].nunique():,}")
        print(
            f"Latest game date: "
            f"{df['GAME_DATE'].max().date()}"
        )

    finally:
        for file in [
            TEMP_CSV,
            TEMP_PARQUET,
            TEMP_PLAYERS
        ]:
            if file.exists():
                file.unlink()


if __name__ == "__main__":
    main()
