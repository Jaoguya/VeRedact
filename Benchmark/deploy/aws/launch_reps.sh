#!/usr/bin/env bash
# Start a full run split by experiment over the workers in deploy/aws/.workers (provision_workers.sh), in the order of
# src/veredact_bench/utils/run_plan.py: worker 1 = e1 (Experiment 1 of every run, with the provers), then one worker
# per other part and run. The provers are launched from here into e1's subnet and stop themselves 15 min after use.
# Older experiment-tier results here move aside first. All detached; each worker powers itself off.
# Later: collect_reps.sh <runs>, then teardown_workers.sh.
# Usage: [TIER=smoke] [ONLY="3 7"] [FORCE=--force] deploy/aws/launch_reps.sh <single|R>   (R >= 3)
#   ONLY: (re)start only these workers (a failed part is rerun whole: with FORCE=--force; e1 gets new provers)
set -euo pipefail
cd "$(dirname "$0")/../.."
ARG=${1:?usage: $0 <single|R>}; R=$ARG; [[ $R == single ]] && R=1
[[ $ARG == single || $R -ge 3 ]] || { echo "R >= 3: the 95 % CI over runs needs at least three"; exit 1; }
TIER=${TIER:-experiment}
PLAN=(); while read -r line; do PLAN+=("$line"); done < <(.venv/bin/python -m veredact_bench.utils.run_plan workers "$R")
[[ $(wc -l < deploy/aws/.workers) -eq ${#PLAN[@]} ]] || { echo "deploy/aws/.workers must list ${#PLAN[@]} workers"; exit 1; }
eval "$(.venv/bin/python deploy/aws/aws_config.py)"
read -r _ _ _ ICOMMIT 2>/dev/null < deploy/aws/.image || true
if [[ $TIER == experiment && -n "${ICOMMIT:-}" ]]; then   # the image (and the synced tree) must be the committed code
  [[ -z "$(git status --porcelain -- .)" && "$ICOMMIT" == "$(git rev-parse --short HEAD)" ]] \
    || { echo "image commit $ICOMMIT != clean HEAD: rebuild it (build_image.sh) or commit"; exit 1; }
fi
KEY="$HOME/.ssh/$AWS_KEY_NAME.pem"
A=(aws --profile "$AWS_PROFILE" --region "$RUN_REGION")
REGION=$RUN_REGION deploy/aws/refresh_ssh_rule.sh >/dev/null
# a worker that powered off (idle watchdog, finished part) is started again; its public IP changes (2026-10-30 smoke)
W=$(mktemp)
while read -r w IID IP; do
  if [[ -z "${ONLY:-}" || " $ONLY " == *" $w "* ]]; then
    state=$("${A[@]}" ec2 describe-instances --instance-ids "$IID" --query 'Reservations[0].Instances[0].State.Name' --output text)
    if [[ $state != running ]]; then
      "${A[@]}" ec2 start-instances --instance-ids "$IID" >/dev/null; "${A[@]}" ec2 wait instance-status-ok --instance-ids "$IID"
      IP=$("${A[@]}" ec2 describe-instances --instance-ids "$IID" --query 'Reservations[0].Instances[0].PublicIpAddress' --output text)
      echo "worker $w was $state: started again at $IP"
    fi
  fi
  echo "$w $IID $IP" >> "$W"
done < deploy/aws/.workers
mv "$W" deploy/aws/.workers
[[ -z "${ONLY:-}" ]] && TIER=$TIER deploy/experiments/supersede_results.sh before_run
start() {   # start <worker n> <instance> <ip>: its part detached; a failure is reported, the others still start
  local runs part ENV=""; read -r runs part <<< "${PLAN[$(( $1 - 1 ))]}"
  if [[ $part == e1 ]]; then
    if REGION=$RUN_REGION SYS_IID=$2 PROVER_HARD_CAP_MIN=$(( R * RUN_PROVER_CAP_MIN_PER_RUN + 90 )) \
         deploy/aws/provision_provers.sh < /dev/null; then
      ENV="VRPQ_PROVER_KEY='$(sed -n 1p deploy/aws/.provers)' VRPQ_PROVERS=$(sed -n 2p deploy/aws/.provers)"
    else
      echo "provers could not be launched: e1 runs without VeRedact-PQ's Exp. 1 systems (coverage gaps)"
    fi
  fi
  ssh -n -i "$KEY" -o StrictHostKeyChecking=accept-new -o ConnectTimeout=10 "$AWS_SSH_USER@$3" \
    "cd $REPO_REMOTE_DIR/Benchmark && mkdir -p results/logs && ($ENV TIER=$TIER FORCE=${FORCE:-} \
     REP_HARD_CAP_MIN=$([[ $part == e1 ]] && echo $(( R * RUN_E1_CAP_MIN_PER_RUN + 60 )) || echo "$RUN_PART_CAP_MIN") \
     setsid nohup deploy/experiments/rep_run.sh $runs $part > results/logs/rep_run_${runs//,/-}_$part.out 2>&1 < /dev/null &)" \
    && echo "worker $1: runs $runs part $part started" || echo "worker $1 ($3): START FAILED (stopped? restart it, then ONLY=$1)"
}
E1=""
while read -r w IID IP; do   # every other part first: e1 then waits for the provers (~15 min) without idling them
  [[ -n "${ONLY:-}" && " $ONLY " != *" $w "* ]] && continue
  if [[ $w == 1 ]]; then E1="$w $IID $IP"; else start "$w" "$IID" "$IP"; fi
done < deploy/aws/.workers
[[ -n "$E1" ]] && start $E1
exit 0
