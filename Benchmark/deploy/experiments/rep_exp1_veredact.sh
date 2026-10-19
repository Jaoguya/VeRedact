#!/usr/bin/env bash
# On the COORDINATOR (veredact-bench): VeRedact-PQ's Exp. 1 for repetitions 1..R, one after another, with ONE
# pair of prover hosts (the vCPU quota allows one pair: 2 x 192 vCPUs). Every repetition runs on this server
# alone, so no other experiment shares its cores. Results: results/exp01_redaction_throughput/veredact/experiment-repNN/.
#   setsid nohup deploy/experiments/rep_exp1_veredact.sh <R> > results/logs/rep_exp1.out 2>&1 &
set -uo pipefail
cd "$(dirname "$0")/../.."
R=${1:?usage: $0 <reps>}
sudo shutdown -h +${REP_HARD_CAP_MIN:-720} veredact-rep-exp1-hard-cap
echo "exp1 veredact x $R start $(date -u +%FT%TZ)"
# ~20 min per repetition + bootstrap: the provers' own hard cap must outlast the loop
PROVER_HARD_CAP_MIN=$(( R * 30 + 60 )) deploy/server/provision_provers_local.sh "${PROVER_COUNT:-2}" "${PROVER_TYPE:-c7i.48xlarge}" \
  || { echo "provers could not be launched"; deploy/server/teardown_provers_local.sh; echo DONE; sudo shutdown -h +2; exit 1; }
export VRPQ_PROVER_KEY=$(sed -n 1p deploy/aws/.provers) VRPQ_PROVERS=$(sed -n 2p deploy/aws/.provers)
for r in $(seq 1 "$R"); do
  VRPQ_REP=$r SYSTEMS=veredact deploy/experiments/run_experiments.sh experiment exp01_redaction_throughput
  echo "REP${r}_EXIT=$? $(test -f results/exp01_redaction_throughput/veredact/experiment-rep$(printf %02d $r)/metrics.json && echo metrics-ok || echo METRICS-MISSING)"
done
deploy/server/teardown_provers_local.sh
echo "exp1 veredact end $(date -u +%FT%TZ)"
echo DONE
sudo shutdown -h +2 veredact-rep-exp1-done
