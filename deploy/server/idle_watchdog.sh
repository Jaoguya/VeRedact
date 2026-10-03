#!/usr/bin/env bash
# Power the instance off once nothing has run for [run].idle_shutdown_minutes, so a finished (or crashed)
# run stops costing money. Installed by deploy/aws/launch_run.sh as a root cron job (every minute).
# "Busy" = a veredact_bench / run_eval.py / run_experiments / bootstrap process, or an interactive SSH session.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
eval "$(python3 "$ROOT/deploy/aws/aws_config.py")"
STAMP=/var/tmp/veredact-last-busy
if pgrep -f "veredact_bench|run_eval.py|run_experiments.sh|bootstrap_server.sh" >/dev/null || who | grep -q pts/; then
  date +%s > "$STAMP"; exit 0
fi
[[ -f "$STAMP" ]] || { date +%s > "$STAMP"; exit 0; }
idle=$(( ($(date +%s) - $(cat "$STAMP")) / 60 ))
if (( idle >= RUN_IDLE_SHUTDOWN_MINUTES )); then
  logger "veredact idle watchdog: idle ${idle} min -> poweroff"
  /sbin/shutdown -h now
fi
