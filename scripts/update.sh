#!/bin/sh
# Re-downloads Epoch AI data and recomputes the report.
# Example crontab (every Monday at 8am):
#   0 8 * * 1 /path/to/benchlag/scripts/update.sh >> /path/to/benchlag/reports/update.log 2>&1
set -eu
cd "$(dirname "$0")/.."
PATH="/opt/homebrew/bin:$PATH"
echo "=== $(date '+%Y-%m-%d %H:%M') ==="
uv run benchlag
