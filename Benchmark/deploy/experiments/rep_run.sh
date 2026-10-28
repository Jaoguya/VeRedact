#!/usr/bin/env bash
# One part of a full run on a WORKER (provision_workers.sh); parts and workers: src/veredact_bench/utils/run_plan.py
# (fair: an experiment's systems share one machine). e1 = Experiment 1 of every run here: VeRedact-PQ's four systems
# with the provers (VRPQ_PROVERS/VRPQ_PROVER_KEY) for run 1, 2, ..., then the baselines for run 1, 2, ...
# <runs>: single (results/.../experiment/) | r | 1,2,3 (experiment-repNN/). TIER=smoke: plumbing check only.
# Ends with DONE and powers off (stop: results stay on disk until collect_reps.sh).
#   setsid nohup deploy/experiments/rep_run.sh <single|r|1,2,3> <part> > results/logs/rep_run.out 2>&1 &
set -uo pipefail
cd "$(dirname "$0")/../.."
RUNS=${1:?usage: $0 <single|r|1,2,3> <part>}; PART=${2:?usage: $0 <single|r|1,2,3> <part>}
TIER=${TIER:-experiment}
export SKIP_TABLES=1   # tables/figures come from collect_reps.sh once every part is in
EXPS=$(.venv/bin/python -m veredact_bench.utils.run_plan experiments "$PART") || { echo "unknown part $PART"; exit 1; }
VRPQ_EXP1=veredact,veredact-per-request,veredact-fixed-batch,veredact-cora-no-sfmr  # every system that proves
n=$(tr ',' '\n' <<< "$RUNS" | wc -l)
# hard cap: REP_HARD_CAP_MIN from launch_reps.sh (configs/aws.toml [run] caps); the defaults are the same values
sudo shutdown -h +${REP_HARD_CAP_MIN:-$([[ $PART == e1 ]] && echo $(( n * 300 + 60 )) || echo 720)} veredact-rep-hard-cap
run_of() { if [[ $1 == single ]]; then unset VRPQ_REP; else export VRPQ_REP=$1; fi; }
echo "runs $RUNS part $PART ($TIER) start $(date -u +%FT%TZ)"
if [[ $PART == e1 ]]; then
  if [[ -n "${VRPQ_PROVERS:-}" ]]; then
    for r in ${RUNS//,/ }; do
      run_of "$r"; SYSTEMS=$VRPQ_EXP1 deploy/experiments/run_experiments.sh "$TIER" $EXPS
      echo "STEP1_RUN${r}_EXIT=$?"
    done
  else
    echo "STEP1: no prover hosts - VeRedact-PQ's Exp. 1 systems are NOT run (see coverage gaps)"
  fi
  unset VRPQ_PROVERS VRPQ_PROVER_KEY
  export VRPQ_SKIP=$(sed 's/[^,]*/exp01_redaction_throughput:&/g' <<< "$VRPQ_EXP1")   # done above with provers
fi
for r in ${RUNS//,/ }; do
  run_of "$r"; deploy/experiments/run_experiments.sh "$TIER" $EXPS
  echo "RUN${r}_EXIT=$?"
  VRPQ_SKIP= .venv/bin/python scripts/check_coverage.py --tier "$TIER"   # no skip: missing provers show as gaps
  echo "COV${r}_EXIT=$?"
done
echo "runs $RUNS part $PART end $(date -u +%FT%TZ)"
echo DONE
sudo shutdown -h +2 veredact-rep-done
