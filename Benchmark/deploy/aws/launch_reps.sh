#!/usr/bin/env bash
# Start a full run split by experiment over the workers in deploy/aws/.workers (provision_workers.sh), in the order of
# src/veredact_bench/utils/run_plan.py: the e1 workers first (Experiment 1, each with its own prover pair), then one
# worker per other part and run. Provers first, spot only: each e1 worker's pair is tried in its zone, then the
# others; if it only fits elsewhere, that e1 worker is replaced there (provers and e1 share a zone). No spot for a
# pair: nothing starts (the provers launched are terminated). Older results here move aside first. All detached;
# each worker powers itself off. Later: collect_reps.sh <runs>, then teardown_workers.sh.
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
subnet_of() { "${A[@]}" ec2 describe-instances --instance-ids "$1" --query 'Reservations[0].Instances[0].SubnetId' --output text; }
zone_of() { "${A[@]}" ec2 describe-subnets --subnet-ids "$1" --query 'Subnets[0].AvailabilityZone' --output text; }
ALL_SUBNETS=$("${A[@]}" ec2 describe-subnets --filters Name=default-for-az,Values=true --query 'Subnets[].SubnetId' --output text)
selected() { [[ -z "${ONLY:-}" || " $ONLY " == *" $1 "* ]]; }
# ---- provers first: one spot pair per e1 worker, in its zone (or the e1 worker moves to the pair's zone) -----------
while read -r w IID IP; do
  read -r runs part <<< "${PLAN[$(( w - 1 ))]}"
  [[ $part == e1 ]] && selected "$w" || continue
  n=$(tr ',' '\n' <<< "$runs" | wc -l | tr -d ' ')
  own=$(subnet_of "$IID"); ok=""
  for sn in $own ${ALL_SUBNETS//$own/}; do
    if REGION=$RUN_REGION SYS_IID=$IID SUBNET_ID=$sn PROVERS_FILE=deploy/aws/.provers_w$w \
         PROVER_HARD_CAP_MIN=$(( n * RUN_PROVER_CAP_MIN_PER_RUN + 90 )) deploy/aws/provision_provers.sh < /dev/null; then
      ok=$sn; break
    fi
  done
  if [[ -z "$ok" ]]; then
    echo "no spot capacity for worker $w's prover pair in any zone: nothing is started (retry later)"
    REGION=$RUN_REGION deploy/aws/teardown_provers.sh; exit 1
  fi
  if [[ $ok != "$own" ]]; then   # the pair fits only in another zone: the e1 worker follows it
    T=$(mktemp); ZONE=$(zone_of "$ok") WORKERS_FILE=$T deploy/aws/provision_workers.sh 1 < /dev/null \
      || { echo "no spot e1 worker next to the provers: nothing is started"; REGION=$RUN_REGION deploy/aws/teardown_provers.sh; exit 1; }
    read -r _ NIID NIP < "$T"; rm -f "$T"
    SIR=$("${A[@]}" ec2 describe-instances --instance-ids "$IID" --query 'Reservations[0].Instances[0].SpotInstanceRequestId' --output text)
    if [[ -n "$SIR" && "$SIR" != None ]]; then "${A[@]}" ec2 cancel-spot-instance-requests --spot-instance-request-ids "$SIR" >/dev/null; fi
    "${A[@]}" ec2 terminate-instances --instance-ids "$IID" >/dev/null
    W2=$(mktemp); awk -v w="$w" -v l="$w $NIID $NIP" '$1 == w {print l; next} {print}' deploy/aws/.workers > "$W2" && mv "$W2" deploy/aws/.workers
    echo "worker $w moved to $(zone_of "$ok") next to its provers: $NIID $NIP"
  fi
done < <(cat deploy/aws/.workers)
# ---- then every part, e1 last (its provers are up) ---------------------------------------------------------------
start() {   # start <worker n> <ip>: its part detached; a failure is reported, the others still start
  local runs part n ENV=""; read -r runs part <<< "${PLAN[$(( $1 - 1 ))]}"
  n=$(tr ',' '\n' <<< "$runs" | wc -l | tr -d ' ')
  [[ $part == e1 ]] && ENV="VRPQ_PROVER_KEY='$(sed -n 1p deploy/aws/.provers_w$1)' VRPQ_PROVERS=$(sed -n 2p deploy/aws/.provers_w$1)"
  ssh -n -i "$KEY" -o StrictHostKeyChecking=accept-new -o ConnectTimeout=10 "$AWS_SSH_USER@$2" \
    "cd $REPO_REMOTE_DIR/Benchmark && mkdir -p results/logs && ($ENV TIER=$TIER FORCE=${FORCE:-} \
     REP_HARD_CAP_MIN=$([[ $part == e1 ]] && echo $(( n * RUN_E1_CAP_MIN_PER_RUN + 60 )) || echo "$RUN_PART_CAP_MIN") \
     setsid nohup deploy/experiments/rep_run.sh $runs $part > results/logs/rep_run_${runs//,/-}_$part.out 2>&1 < /dev/null &)" \
    && echo "worker $1: runs $runs part $part started" || echo "worker $1 ($2): START FAILED (restart: ONLY=$1)"
}
E1=()
while read -r w IID IP; do
  selected "$w" || continue
  read -r _ part <<< "${PLAN[$(( w - 1 ))]}"
  if [[ $part == e1 ]]; then E1+=("$w $IP"); else start "$w" "$IP"; fi
done < deploy/aws/.workers
for i in ${E1[@]+"${!E1[@]}"}; do start ${E1[$i]}; done
exit 0
