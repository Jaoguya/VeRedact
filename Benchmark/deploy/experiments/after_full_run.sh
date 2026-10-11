#!/usr/bin/env bash
# Runs next to full_run.sh (started separately, so the running script is never edited): waits for the run's
# end marker, cancels its 2-min shutdown, writes tables + figures, then powers off. Hard cap: power off at
# HARD_CAP_UTC (default 06:00 UTC next day) whatever happens, so a hung run never keeps the server up.
#   setsid nohup deploy/experiments/after_full_run.sh results/logs/full_run_<id>.out > results/logs/after_full_run.out 2>&1 &
set -uo pipefail
cd "$(dirname "$0")/../.."
LOG=$1
CAP=$(date -u -d "${HARD_CAP_UTC:-tomorrow 06:00}" +%s)
while ! grep -q '^DONE' "$LOG" 2>/dev/null; do
  if (( $(date -u +%s) >= CAP )); then echo "hard cap reached $(date -u +%FT%TZ): power off"; sudo shutdown -h now; exit 0; fi
  if ! pgrep -f deploy/experiments/full_run.sh >/dev/null; then echo "full_run.sh gone without DONE $(date -u +%FT%TZ)"; break; fi
  sleep 20
done
sudo shutdown -c 2>/dev/null
echo "making tables + figures $(date -u +%FT%TZ)"
timeout 1800 .venv/bin/python scripts/make_tables.py --tier experiment; echo "TABLES_EXIT=$?"
timeout 1800 .venv/bin/python scripts/make_figures.py --tier experiment; echo "FIGURES_EXIT=$?"
echo "power off $(date -u +%FT%TZ)"
sudo shutdown -h now
