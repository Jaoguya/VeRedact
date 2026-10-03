#!/usr/bin/env bash
# Run experiments for one tier, end to end, on the machine you are logged into.
#   1. config check (refuses to continue on errors)
#   2. ledger.backend = besu -> start the Besu QBFT network shaped by the tier's ledger section
#   3. scripts/run_eval.py --tier <tier> --experiment <ids|all>  -> results/<exp>/<method>/<tier>/  (log tee'd)
#   4. scripts/make_tables.py + make_figures.py -> paper/; results + paper synced to [run].s3_uri when set;
#      Besu stopped (KEEP_BESU=1 keeps it)
# Usage: deploy/experiments/run_experiments.sh <smoke|pilot|experiment> [exp01_redaction_throughput ... | all]
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
TIER=${1:?usage: $0 <smoke|pilot|experiment> [experiment ids ... | all]}; shift
EXPS=${*:-all}
export TIER
PY="$ROOT/.venv/bin/python"
[[ -x "$PY" ]] || { echo "missing $PY — run deploy/server/bootstrap_server.sh or make venv"; exit 1; }
[[ "$TIER" == experiment ]] && export VRPQ_SIG_BACKEND=oqs   # the runner refuses any other backend in this tier
eval "$("$PY" deploy/aws/aws_config.py)"

"$PY" scripts/validate_config.py "$TIER"
if [[ "$LEDGER_BACKEND" == besu ]]; then
  export VRPQ_BESU_KEY="$BESU_DEV_PRIVATE_KEY"   # public dev key, funded only in the private genesis
  deploy/besu/start_besu_network.sh
  [[ "${KEEP_BESU:-0}" == 1 ]] || trap 'deploy/besu/stop_besu_network.sh' EXIT
fi

mkdir -p results/logs
LOG="results/logs/${TIER}_${EXPS// /_}_$(date +%Y%m%d-%H%M%S).log"
echo "running $EXPS on tier $TIER (ledger=$LEDGER_BACKEND) -> $LOG"
"$PY" scripts/run_eval.py --tier "$TIER" --experiment $EXPS 2>&1 | tee "$LOG"
{ "$PY" scripts/make_tables.py --tier "$TIER" && "$PY" scripts/make_figures.py --tier "$TIER"; } 2>&1 | tee -a "$LOG" \
  || echo "tables/figures failed (results are intact)"
if [[ -n "${RUN_S3_URI}" ]]; then
  aws s3 sync results "$RUN_S3_URI/results/$(hostname)" --only-show-errors
  aws s3 sync paper "$RUN_S3_URI/paper/$(hostname)" --only-show-errors
fi
echo "done: results/ paper/"
