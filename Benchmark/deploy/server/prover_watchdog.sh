#!/usr/bin/env bash
# Prover host self-termination (cron, every minute; the instance's shutdown behaviour is "terminate"):
#   used once (a connection on PORT was seen) and idle for 15 min -> shut down
#   never used within 45 min of boot -> shut down
# provision_provers.sh also sets an unconditional 4 h shutdown.
set -uo pipefail
PORT=${1:-7700}
STATE=/var/tmp/veredact-prover
mkdir -p "$STATE"
now=$(date +%s)
boot=$(date -d "$(uptime -s)" +%s)
if ss -Htn state established "( sport = :$PORT )" | grep -q .; then
  echo "$now" > "$STATE/last"; touch "$STATE/used"; exit 0
fi
if [[ -f "$STATE/used" ]]; then
  idle=$(( (now - $(cat "$STATE/last")) / 60 ))
  (( idle >= 15 )) && { logger "veredact prover idle ${idle} min -> shutdown"; /sbin/shutdown -h now; }
else
  (( (now - boot) / 60 >= 45 )) && { logger "veredact prover never used -> shutdown"; /sbin/shutdown -h now; }
fi
exit 0
