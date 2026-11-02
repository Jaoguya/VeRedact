#!/usr/bin/env bash
# Start a full run split by experiment over the workers in deploy/aws/.workers (provision_workers.sh), in the order of
# src/veredact_bench/utils/run_plan.py (hybrid plan: Exp. 0 + 1 in run 1 only). Every part except e1 first, then
# the provers (on demand, [run] prover_pools): the e1 worker's pool is tried in its zone, then the others; if it only
# fits elsewhere, the e1 worker is replaced there (provers and e1 share a zone). No pool: e1 does not start (launched
# provers are terminated). Older results here move aside first. All detached; each worker powers itself off. Later: collect_reps.sh <runs>, then teardown_workers.sh.
# Usage: [TIER=smoke] [ONLY="3 7"] [FORCE=--force] deploy/aws/launch_reps.sh <single|R>   (R >= 3)
#   ONLY: (re)start only these workers (a failed part is rerun whole: with FORCE=--force; e1 gets new provers)
set -euo pipefail
cd "$(dirname "$0")/../.."
. deploy/aws/remote_lib.sh   # retries: a sleeping laptop pauses the launch, never breaks it
ARG=${1:?usage: $0 <single|R>}; R=$ARG; [[ $R == single ]] && R=1
[[ $ARG == single || $R -ge 3 ]] || { echo "R >= 3: the 95 % CI over runs needs at least three"; exit 1; }
TIER=${TIER:-experiment}
PLAN=(); while read -r line; do PLAN+=("$line"); done < <(.venv/bin/python -m veredact_bench.utils.run_plan workers "$R")
[[ $(wc -l < deploy/aws/.workers) -eq ${#PLAN[@]} ]] || { echo "deploy/aws/.workers must list ${#PLAN[@]} workers"; exit 1; }
eval "$(.venv/bin/python deploy/aws/aws_config.py)"
read -r _ _ _ ICOMMIT 2>/dev/null < deploy/aws/.image || true
if [[ $TIER == experiment && -n "${ICOMMIT:-}" ]]; then   # the image (and the synced tree) must be the committed code
  # Benchmark/ only: a docs commit outside it (TASK.md, HANDOFF.md) moves HEAD but not the code the image holds
  [[ -z "$(git status --porcelain -- .)" && "$(git rev-parse "$ICOMMIT:./")" == "$(git rev-parse HEAD:./)" ]] \
    || { echo "Benchmark/ differs from image commit $ICOMMIT (or is uncommitted): rebuild it (build_image.sh) or commit"; exit 1; }
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
# ---- every part except e1 first: they need no provers, so they never sit idle while the provers set up ----------
running_ip() {   # running_ip <worker n>: its IP, started again if its idle watchdog stopped it (laptop asleep, waits)
  local w=$1 IID IP state
  read -r _ IID IP < <(awk -v w="$w" '$1 == w' deploy/aws/.workers)
  state=$(retry "${A[@]}" ec2 describe-instances --instance-ids "$IID" --query 'Reservations[0].Instances[0].State.Name' --output text)
  if [[ $state != running ]]; then
    [[ $state == stopping ]] && { retry "${A[@]}" ec2 wait instance-stopped --instance-ids "$IID" || true; }
    retry "${A[@]}" ec2 start-instances --instance-ids "$IID" >/dev/null; retry "${A[@]}" ec2 wait instance-status-ok --instance-ids "$IID"
    IP=$(retry "${A[@]}" ec2 describe-instances --instance-ids "$IID" --query 'Reservations[0].Instances[0].PublicIpAddress' --output text)
    W2=$(mktemp); awk -v w="$w" -v l="$w $IID $IP" '$1 == w {print l; next} {print}' deploy/aws/.workers > "$W2" && mv "$W2" deploy/aws/.workers
  fi
  echo "$IP"
}
start() {   # start <worker n>: its part detached; a failure is reported, the others still start
  local runs part n ENV="" ip; read -r runs part <<< "${PLAN[$(( $1 - 1 ))]}"
  n=$(tr ',' '\n' <<< "$runs" | wc -l | tr -d ' ')
  [[ $part == e1 ]] && ENV="VRPQ_PROVER_KEY='$(sed -n 1p deploy/aws/.provers_w$1)' VRPQ_PROVERS=$(sed -n 2p deploy/aws/.provers_w$1)"
  ip=$(running_ip "$1")
  retry ssh -n -i "$KEY" -o StrictHostKeyChecking=accept-new -o ConnectTimeout=10 "$AWS_SSH_USER@$ip" \
    "cd $REPO_REMOTE_DIR/Benchmark && mkdir -p results/logs && ($ENV TIER=$TIER FORCE=${FORCE:-} \
     REP_HARD_CAP_MIN=$([[ $part == e1 ]] && echo $(( n * RUN_E1_CAP_MIN_PER_RUN + 60 )) || echo "$RUN_PART_CAP_MIN") \
     setsid nohup deploy/experiments/rep_run.sh $runs $part > results/logs/rep_run_${runs//,/-}_$part.out 2>&1 < /dev/null &)" \
    && echo "worker $1: runs $runs part $part started" || echo "worker $1 ($ip): START FAILED (restart: ONLY=$1)"
}
while read -r w _ _; do
  selected "$w" || continue
  read -r _ part <<< "${PLAN[$(( w - 1 ))]}"
  [[ $part == e1 ]] || start "$w"
done < <(cat deploy/aws/.workers)
# ---- provers first: the e1 worker's pool, in its zone (or the e1 worker moves to the pool's zone) ----
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
    echo "worker $w's prover pool could not be started in any zone (capacity or set-up: see above); e1 NOT started"
    REGION=$RUN_REGION deploy/aws/teardown_provers.sh; exit 1
  fi
  if [[ $ok != "$own" ]]; then   # the pool fits only in another zone: the e1 worker follows it
    T=$(mktemp); ZONE=$(zone_of "$ok") WORKERS_FILE=$T deploy/aws/provision_workers.sh 1 < /dev/null \
      || { echo "no e1 worker next to the provers: nothing is started"; REGION=$RUN_REGION deploy/aws/teardown_provers.sh; exit 1; }
    read -r _ NIID NIP < "$T"; rm -f "$T"
    "${A[@]}" ec2 terminate-instances --instance-ids "$IID" >/dev/null
    W2=$(mktemp); awk -v w="$w" -v l="$w $NIID $NIP" '$1 == w {print l; next} {print}' deploy/aws/.workers > "$W2" && mv "$W2" deploy/aws/.workers
    echo "worker $w moved to $(zone_of "$ok") next to its provers: $NIID $NIP"
  fi
done < <(cat deploy/aws/.workers)
# ---- then e1 (its provers are up) --------------------------------------------------------------------------------
while read -r w _ _; do
  selected "$w" || continue
  read -r _ part <<< "${PLAN[$(( w - 1 ))]}"
  [[ $part == e1 ]] && start "$w"
done < <(cat deploy/aws/.workers)
exit 0
