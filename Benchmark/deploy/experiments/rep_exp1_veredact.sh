#!/usr/bin/env bash
# On the COORDINATOR (veredact-bench): VeRedact-PQ's Exp. 1 (and its three Exp. 1 variants) for repetitions 1..R, one after another, with ONE
# pair of prover hosts (the vCPU quota allows one pair: 2 x 192 vCPUs). Every repetition runs on this server
# alone, so no other experiment shares its cores. Results: results/exp01_redaction_throughput/<system>/experiment-repNN/.
# <R> = single: one run into results/.../experiment/ (rep 1's seed, no repetition folders).
#   setsid nohup deploy/experiments/rep_exp1_veredact.sh <R|single> > results/logs/rep_exp1.out 2>&1 &
set -uo pipefail
cd "$(dirname "$0")/../.."
R=${1:?usage: $0 <reps|single>}
REPS=$(seq 1 "$R" 2>/dev/null); [[ $R == single ]] && { R=1; REPS=single; }
export SKIP_TABLES=1   # tables/figures come from collect_reps.sh once every part is in
VRPQ_EXP1=veredact,veredact-per-request,veredact-fixed-batch,veredact-cora-no-sfmr  # every system that proves (= full_run.sh)
# ~1.5 h per repetition (four systems x ~20 min measured for one, 2.5 h allowed) + bootstrap: the provers' own hard cap must outlast the loop
sudo shutdown -h +${REP_HARD_CAP_MIN:-$(( R * 150 + 120 ))} veredact-rep-exp1-hard-cap
echo "exp1 veredact x $R start $(date -u +%FT%TZ)"
PROVER_HARD_CAP_MIN=$(( R * 150 + 60 )) deploy/server/provision_provers_local.sh "${PROVER_COUNT:-2}" "${PROVER_TYPE:-c7i.48xlarge}" \
  || { echo "provers could not be launched"; deploy/server/teardown_provers_local.sh; echo DONE; sudo shutdown -h +2; exit 1; }
export VRPQ_PROVER_KEY=$(sed -n 1p deploy/aws/.provers) VRPQ_PROVERS=$(sed -n 2p deploy/aws/.provers)
for r in $REPS; do
  if [[ $r == single ]]; then d=experiment; unset VRPQ_REP; else d=experiment-rep$(printf %02d $r); export VRPQ_REP=$r; fi
  SYSTEMS=$VRPQ_EXP1 deploy/experiments/run_experiments.sh experiment exp01_redaction_throughput
  echo "REP${r}_EXIT=$?"
  for m in ${VRPQ_EXP1//,/ }; do
    echo "  $m $(test -f results/exp01_redaction_throughput/$m/$d/metrics.json && echo metrics-ok || echo METRICS-MISSING)"
  done
done
deploy/server/teardown_provers_local.sh
echo "exp1 veredact end $(date -u +%FT%TZ)"
echo DONE
sudo shutdown -h +2 veredact-rep-exp1-done
