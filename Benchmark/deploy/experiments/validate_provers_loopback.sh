#!/usr/bin/env bash
# Audit A4 check on one host: prover service (pinned to the requester cores) on loopback + Besu + one Exp. 1
# point of VeRedact-PQ through the remote-prover path. Output: results/logs/validate_a4_loopback.out
set -uo pipefail
cd "$(dirname "$0")/../.."
export VRPQ_SIG_BACKEND=oqs TIER=pilot VRPQ_PROVER_KEY="loopback-$RANDOM" VRPQ_PROVERS=127.0.0.1:7700
eval "$(.venv/bin/python deploy/aws/aws_config.py)"
export VRPQ_BESU_KEY=$BESU_DEV_PRIVATE_KEY
taskset -c 0-3,8-11 .venv/bin/python scripts/prover_service.py --port 7700 --workers 8 > results/logs/prover_loopback.log 2>&1 &
PS=$!
trap 'kill $PS 2>/dev/null; deploy/besu/stop_besu_network.sh >/dev/null 2>&1' EXIT
deploy/besu/start_besu_network.sh >/dev/null 2>&1
for n in $(docker ps --format '{{.Names}}' | grep besu-validator); do docker update --cpuset-cpus 4-7,12-15 "$n" >/dev/null; done
sleep 2
# the system on the other cores: on one host this stands in for separate prover machines
taskset -c 4-7,12-15 .venv/bin/python -u scripts/validate_a3.py --rates ${RATES:-100} --skews ${SKEWS:-0.8}
echo "EXIT=$?"
