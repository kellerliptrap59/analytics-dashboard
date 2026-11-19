import pandas as pd

df = pd.read_csv("nba_player_boxscores_2026-27.csv")

players = df["PLAYER_NAME"].dropna().unique()

players_df = pd.DataFrame(players, columns=["PLAYER_NAME"])

players_df = players_df.sort_values("PLAYER_NAME")

players_df.to_csv("nba_player.csv", index=False)