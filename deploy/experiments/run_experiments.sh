#!/usr/bin/env bash
# Run experiments for one config tier, end to end, on the machine you are logged into.
#   1. validate-config (refuses to continue on errors)
#   2. ledger.backend = besu -> start the Besu QBFT network shaped by config/<tier>.toml [ledger]
#   3. python -m veredact_bench run <exps> --config config/<tier>.toml   (tee'd to results/logs/)
#   4. plots; results synced to [run].s3_uri when set; Besu stopped (KEEP_BESU=1 keeps it)
# Usage: deploy/experiments/run_experiments.sh <smoke|pilot|experiment> [exp1 exp2 ... | all]
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
TIER=${1:?usage: $0 <smoke|pilot|experiment> [exp1 ... | all]}; shift
EXPS=${*:-all}
export CONFIG="config/$TIER.toml"
PY="$ROOT/benchmark/.venv/bin/python"
[[ -x "$PY" ]] || { echo "missing $PY — run deploy/server/bootstrap_server.sh or make venv"; exit 1; }
[[ "$TIER" == experiment ]] && export VRPQ_SIG_BACKEND=oqs   # the CLI refuses any other backend in this tier
eval "$(python3 deploy/aws/aws_config.py)"

"$PY" -m veredact_bench.validate_config "$CONFIG"
BACKEND=$(python3 -c "import tomllib;print(tomllib.load(open('$CONFIG','rb'))['ledger']['backend'])")
if [[ "$BACKEND" == besu ]]; then
  export VRPQ_BESU_KEY="$BESU_DEV_PRIVATE_KEY"   # public dev key, funded only in the private genesis
  deploy/besu/start_besu_network.sh
  [[ "${KEEP_BESU:-0}" == 1 ]] || trap 'deploy/besu/stop_besu_network.sh' EXIT
fi

mkdir -p results/logs
LOG="results/logs/${TIER}_${EXPS// /_}_$(date +%Y%m%d-%H%M%S).log"
echo "running $EXPS on tier $TIER (ledger=$BACKEND) -> $LOG"
"$PY" -m veredact_bench run $EXPS --config "$CONFIG" 2>&1 | tee "$LOG"
"$PY" -m veredact_bench.plot 2>&1 | tee -a "$LOG" || echo "plotting failed (results are intact)"
if [[ -n "${RUN_S3_URI}" ]]; then
  aws s3 sync results "$RUN_S3_URI/results/$(hostname)" --only-show-errors
  aws s3 sync plot "$RUN_S3_URI/plot/$(hostname)" --only-show-errors
fi
echo "done: results/ plot/"
