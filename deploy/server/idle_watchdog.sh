#!/usr/bin/env bash
# Power the instance off once nothing has run for [run].idle_shutdown_minutes, so a finished (or crashed)
# run stops costing money. Installed by deploy/aws/launch_run.sh as a root cron job (every minute).
# "Busy" = a veredact_bench / run_eval.py / run_experiments / bootstrap process, or an interactive SSH session.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
# the venv python: aws_config.py imports veredact_bench (system python3 cannot, so the watchdog used to exit
# under set -u before ever checking idleness — instance left running 7 h on 2026-10-04)
if ! cfg=$("$ROOT/.venv/bin/python" "$ROOT/deploy/aws/aws_config.py" 2>&1); then
  logger "veredact idle watchdog: config unreadable, using 30 min: ${cfg##*$'\n'}"
  cfg=""
fi
eval "$cfg"
MINUTES=${RUN_IDLE_SHUTDOWN_MINUTES:-30}  # fail safe: an unreadable config must not disable the shutdown
STAMP=/var/tmp/veredact-last-busy
if pgrep -f "veredact_bench|run_eval.py|scripts/diag_|run_experiments.sh|bootstrap_server.sh" >/dev/null || who | grep -q pts/; then
  date +%s > "$STAMP"; exit 0
fi
[[ -f "$STAMP" ]] || { date +%s > "$STAMP"; exit 0; }
# idle since the later of the last busy minute and this boot: the stamp survives a stop/start (/var/tmp), and
# an old stamp powered the instance off one minute after boot, before launch_run.sh could connect (2026-10-04)
boot=$(date -d "$(uptime -s)" +%s)
last=$(cat "$STAMP"); (( boot > last )) && last=$boot
idle=$(( ($(date +%s) - last) / 60 ))
if (( idle >= MINUTES )); then
  logger "veredact idle watchdog: idle ${idle} min -> poweroff"
  /sbin/shutdown -h now
fi
