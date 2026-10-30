#!/usr/bin/env bash
# Launch N workers for a split full run (configs/aws.toml [run] region; worker 1 = e1 alone in [run] zone first),
# identical to veredact-bench (type, volume), tagged Name=veredact-rep-worker, bootstrapped in parallel with this tree
# (QUICK=1 from a prebuilt image, deploy/aws/.image). Creates once in the region: key pair and security group
# veredact-bench (SSH from this IP only, all TCP inside the group). Writes WORKERS_FILE (deploy/aws/.workers).
# Market: [run] market (author 2026-10-30: on demand; WORKER_MARKET overrides). If any worker cannot be launched,
# the ones already launched are terminated.
# Usage: deploy/aws/provision_workers.sh <N>   (env: WORKER_MARKET=ondemand, ZONE, WORKER_NAME, WORKERS_FILE, NO_IMAGE=1)
set -euo pipefail
cd "$(dirname "$0")/../.."
N=${1:?usage: $0 <N>}
eval "$(.venv/bin/python deploy/aws/aws_config.py)"
A=(aws --profile "$AWS_PROFILE" --region "$RUN_REGION")
KEY="$HOME/.ssh/$AWS_KEY_NAME.pem"
NAME=${WORKER_NAME:-veredact-rep-worker}; WF=${WORKERS_FILE:-deploy/aws/.workers}
if ! "${A[@]}" ec2 describe-key-pairs --key-names "$AWS_KEY_NAME" >/dev/null 2>&1; then
  PUBK=$(mktemp); ssh-keygen -y -f "$KEY" > "$PUBK"
  "${A[@]}" ec2 import-key-pair --key-name "$AWS_KEY_NAME" --public-key-material "fileb://$PUBK" >/dev/null; rm -f "$PUBK"
fi
SG=$("${A[@]}" ec2 describe-security-groups --filters "Name=group-name,Values=$AWS_NAME_TAG" --query 'SecurityGroups[0].GroupId' --output text)
if [[ -z "$SG" || "$SG" == None ]]; then
  SG=$("${A[@]}" ec2 create-security-group --group-name "$AWS_NAME_TAG" --description "VeRedact benchmark workers" --query GroupId --output text)
  "${A[@]}" ec2 authorize-security-group-ingress --group-id "$SG" --ip-permissions "IpProtocol=tcp,FromPort=0,ToPort=65535,UserIdGroupPairs=[{GroupId=$SG}]" >/dev/null
fi
REGION=$RUN_REGION deploy/aws/refresh_ssh_rule.sh >/dev/null
QUICK=0; read -r IREG IMG _ 2>/dev/null < deploy/aws/.image || true
if [[ "${NO_IMAGE:-0}" != 1 && "${IREG:-}" == "$RUN_REGION" && -n "${IMG:-}" ]]; then AMI=$IMG; QUICK=1
else AMI=$("${A[@]}" ssm get-parameter --name "$AWS_AMI_SSM_PARAMETER" --query Parameter.Value --output text); fi
SUBNETS=$("${A[@]}" ec2 describe-subnets --filters Name=default-for-az,Values=true \
           --query 'Subnets[].[AvailabilityZone,SubnetId]' --output text | sort | awk -v z="${ZONE:-$RUN_ZONE}" '$1 == z {print $2; next} {o = o " " $2} END {print o}')
# Persistent spot with interruption = stop: a power-off stops (results stay on disk) and a reclaimed worker keeps its
# disk; rerun its part WHOLE (FORCE=--force, deploy/experiments/rep_run.sh). teardown_workers.sh cancels the requests.
MARKETS=("${WORKER_MARKET:-$RUN_MARKET}")
launch() {   # launch <count>: ids of <count> workers, first subnet (zone order) and market with capacity
  local MK SN OPT ids
  for MK in "${MARKETS[@]}"; do
    OPT=(); [[ "$MK" == spot ]] && OPT=(--instance-market-options \
      'MarketType=spot,SpotOptions={SpotInstanceType=persistent,InstanceInterruptionBehavior=stop}')
    for SN in $SUBNETS; do
      ids=$("${A[@]}" ec2 run-instances --image-id "$AMI" --instance-type "$AWS_INSTANCE_TYPE" --count "$1" \
              ${OPT[@]+"${OPT[@]}"} --key-name "$AWS_KEY_NAME" --security-group-ids "$SG" --subnet-id "$SN" \
              --block-device-mappings "DeviceName=/dev/sda1,Ebs={VolumeSize=$AWS_VOLUME_GB,VolumeType=gp3}" \
              --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=$NAME}]" \
              --query 'Instances[].InstanceId' --output text) && { echo "$MK $SN: $ids" >&2; echo "$ids"; return; }
      echo "no $MK capacity for $1 x $AWS_INSTANCE_TYPE in $SN" >&2
    done
  done
  return 1
}
# one worker per request: worker 1 (e1) first, in the run zone if it has room; one request for 12 found no spot in
# any zone (2026-10-30) where single machines may still fit
IIDS=""
abandon() {   # some worker found no capacity: nothing half-launched is left running (spot requests cancelled first)
  [[ -n "${IIDS// /}" ]] || exit 1
  local sirs; sirs=$("${A[@]}" ec2 describe-instances --instance-ids $IIDS --query 'Reservations[].Instances[].SpotInstanceRequestId' --output text)
  if [[ -n "$sirs" && "$sirs" != None ]]; then "${A[@]}" ec2 cancel-spot-instance-requests --spot-instance-request-ids $sirs >/dev/null; fi
  "${A[@]}" ec2 terminate-instances --instance-ids $IIDS >/dev/null
  echo "no capacity for all $N workers: the $(wc -w <<< "$IIDS") launched are terminated; retry later"; exit 1
}
for _ in $(seq 1 "$N"); do id=$(launch 1) || abandon; IIDS="$IIDS $id"; done
IIDS=${IIDS# }
echo "launched (image $AMI): $IIDS"
"${A[@]}" ec2 wait instance-status-ok --instance-ids $IIDS
: > "$WF"
r=0
for IID in $IIDS; do
  r=$((r + 1))
  IP=$("${A[@]}" ec2 describe-instances --instance-ids "$IID" --query 'Reservations[0].Instances[0].PublicIpAddress' --output text)
  echo "$r $IID $IP" >> "$WF"
done
mkdir -p results/logs
while read -r r IID IP; do
  (
    SSH=(ssh -n -i "$KEY" -o StrictHostKeyChecking=accept-new -o ConnectTimeout=10 "$AWS_SSH_USER@$IP")
    for _ in $(seq 1 60); do "${SSH[@]}" true 2>/dev/null && break; sleep 5; done
    "${SSH[@]}" "sudo shutdown -h +$RUN_SETUP_CAP_MIN veredact-setup-cap"   # set-up cap; rep_run.sh replaces it
    scp -q -i "$KEY" -o StrictHostKeyChecking=accept-new deploy/server/bootstrap_server.sh "$AWS_SSH_USER@$IP:/tmp/"
    "${SSH[@]}" "sudo mkdir -p $REPO_REMOTE_DIR/Benchmark && sudo chown -R $AWS_SSH_USER $REPO_REMOTE_DIR"
    rsync -az -e "ssh -i $KEY -o StrictHostKeyChecking=accept-new" --exclude .git --exclude .venv --exclude __pycache__ \
      --exclude target --exclude '/results/*' --exclude .cache --exclude 'deploy/aws/.*' --exclude deploy/besu/.network \
      ./ "$AWS_SSH_USER@$IP:$REPO_REMOTE_DIR/Benchmark/"
    "${SSH[@]}" "sudo QUICK=$QUICK REPO_URL=$REPO_URL REPO_BRANCH=$REPO_BRANCH REMOTE_DIR=$REPO_REMOTE_DIR bash /tmp/bootstrap_server.sh" \
      > "results/logs/worker-bootstrap-$r.log" 2>&1 && echo "worker $r ($IP) bootstrapped" || echo "worker $r ($IP) BOOTSTRAP FAILED"
    "${SSH[@]}" "echo '* * * * * root $REPO_REMOTE_DIR/Benchmark/deploy/server/idle_watchdog.sh' | sudo tee /etc/cron.d/veredact-idle >/dev/null"
  ) &
done < "$WF"
wait
cat "$WF"
