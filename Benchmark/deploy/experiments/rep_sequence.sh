#!/usr/bin/env bash
# Repetitions FROM..TO of the full run, one after another on THIS server (veredact-bench). Each repetition:
#   1. VeRedact-PQ's Exp. 1 with freshly launched prover hosts (terminated right after)
#   2. every other (experiment, system)
#   3. scripts/check_rep.py: coverage + logic checks; a failure STOPS the sequence and powers off, so the fault
#      is fixed before the next repetition is paid for. Restart with FROM = the failed repetition.
# Results: results/<exp>/<method>/experiment-repNN/. Each repetition has a 12 h hard power-off cap.
#   setsid nohup deploy/experiments/rep_sequence.sh <FROM> <TO> > results/logs/rep_sequence.out 2>&1 &
set -uo pipefail
cd "$(dirname "$0")/../.."
FROM=${1:?usage: $0 <from> <to>}; TO=${2:?usage: $0 <from> <to>}
mkdir -p results/logs
for r in $(seq "$FROM" "$TO"); do
  rr=$(printf %02d "$r"); LOG=results/logs/rep_r$rr.out
  sudo shutdown -h +${REP_HARD_CAP_MIN:-720} veredact-rep-hard-cap   # replaced by the next repetition's cap
  {
    echo "rep $r start $(date -u +%FT%TZ)"
    export VRPQ_REP=$r
    if deploy/server/provision_provers_local.sh "${PROVER_COUNT:-2}" "${PROVER_TYPE:-c7i.48xlarge}"; then
      VRPQ_PROVER_KEY=$(sed -n 1p deploy/aws/.provers) VRPQ_PROVERS=$(sed -n 2p deploy/aws/.provers) SYSTEMS=veredact \
        deploy/experiments/run_experiments.sh experiment exp01_redaction_throughput
      echo "STEP1_EXIT=$?"
    else
      echo "STEP1: prover hosts could not be launched"
    fi
    deploy/server/teardown_provers_local.sh
    VRPQ_SKIP=exp01_redaction_throughput:veredact deploy/experiments/run_experiments.sh experiment all
    echo "RUN_EXIT=$?"
    echo "rep $r end $(date -u +%FT%TZ)"
  } > "$LOG" 2>&1
  if VRPQ_REP=$r .venv/bin/python scripts/check_rep.py --tier experiment --logs "$LOG" >> "$LOG" 2>&1; then
    echo "rep $r PASS $(date -u +%FT%TZ)"
  else
    echo "rep $r FAILED - sequence stopped (see $LOG)"; echo DONE; sudo shutdown -h +2 veredact-rep-failed; exit 1
  fi
done
echo "reps $FROM..$TO all passed $(date -u +%FT%TZ)"
echo DONE
sudo shutdown -h +2 veredact-reps-done
