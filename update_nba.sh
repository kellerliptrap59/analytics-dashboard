
#!/bin/bash

# Stop if any command fails
set -e

# Navigate to your project
cd "/Users/kellerliptrap/betting_nba"

# Activate Python environment
source .venv/bin/activate

# Get the latest repository changes
git pull --rebase

# Download and update NBA data
python data/stats.py

# Stage updated CSV files
git add data/*.csv

# Commit and push only if something changed
if ! git diff --cached --quiet; then
    git commit -m "Automatically update NBA data"
    git push
else
    echo "No data changes detected."
fi
