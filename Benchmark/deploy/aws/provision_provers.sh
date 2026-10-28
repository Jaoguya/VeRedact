#!/usr/bin/env bash
# Launch requester prover hosts for Exp. 1 (audit A4) next to veredact-bench (or SYS_IID=<instance> in
# REGION=<region>, e.g. the e1 worker of a split run), bootstrap them and start scripts/prover_service.py.
# Only instances tagged Name=veredact-prover are created (large: they cost money every hour).
#   deploy/aws/provision_provers.sh [count] ["types"]   (defaults: configs/aws.toml [run] prover_count, prover_types)
# Each type on spot in turn, then the last one on demand. A prebuilt image (deploy/aws/.image) in this region
# replaces the Ubuntu image and the full bootstrap. Code lives in REMOTE_DIR/Benchmark, as on the workers.
# Writes deploy/aws/.provers (gitignored): line 1 = VRPQ_PROVER_KEY, line 2 = VRPQ_PROVERS (private ip:7700,...).
set -euo pipefail
cd "$(dirname "$0")/../.."
eval "$(.venv/bin/python deploy/aws/aws_config.py 2>/dev/null || python3 deploy/aws/aws_config.py)"
A=(aws --profile "$AWS_PROFILE" --region "${REGION:-$AWS_REGION}")
N=${1:-$RUN_PROVER_COUNT}; read -ra TYPES <<< "${2:-$RUN_PROVER_TYPES}"; PORT=7700; NAME=veredact-prover
REG=${REGION:-$AWS_REGION}; BENCH=$REPO_REMOTE_DIR/Benchmark
KEY_FILE="$HOME/.ssh/$AWS_KEY_NAME.pem"
[[ -n "${SYS_IID:-}" ]] || read -r SYS_IID _ < deploy/aws/.instance
SYS_SG=$("${A[@]}" ec2 describe-instances --instance-ids "$SYS_IID" \
          --query 'Reservations[0].Instances[0].SecurityGroups[0].GroupId' --output text)
SUBNET=$("${A[@]}" ec2 describe-instances --instance-ids "$SYS_IID" --query 'Reservations[0].Instances[0].SubnetId' --output text)
CIDR="$(curl -fsS https://checkip.amazonaws.com)/32"

echo "[1/5] security group $NAME (port $PORT from veredact-bench only, SSH from $CIDR)"
SG=$("${A[@]}" ec2 describe-security-groups --filters "Name=group-name,Values=$NAME" \
       --query 'SecurityGroups[0].GroupId' --output text 2>/dev/null || true)
if [[ -z "$SG" || "$SG" == None ]]; then
  SG=$("${A[@]}" ec2 create-security-group --group-name "$NAME" --description "VeRedact requester provers" \
         --query GroupId --output text)
  "${A[@]}" ec2 authorize-security-group-ingress --group-id "$SG" \
    --ip-permissions "IpProtocol=tcp,FromPort=$PORT,ToPort=$PORT,UserIdGroupPairs=[{GroupId=$SYS_SG}]" >/dev/null
fi
"${A[@]}" ec2 authorize-security-group-ingress --group-id "$SG" --protocol tcp --port 22 --cidr "$CIDR" >/dev/null 2>&1 || true

echo "[2/5] launch $N x ${TYPES[*]} (same subnet as the system under test)"
QUICK=0; read -r IREG IMG _ < deploy/aws/.image 2>/dev/null || true
if [[ "${IREG:-}" == "$REG" && -n "${IMG:-}" ]]; then AMI=$IMG; QUICK=1
else AMI=$("${A[@]}" ssm get-parameter --name "$AWS_AMI_SSM_PARAMETER" --query Parameter.Value --output text); fi
IIDS=""
TRIES=(); for T in "${TYPES[@]}"; do TRIES+=("$T spot"); done; TRIES+=("${TYPES[${#TYPES[@]}-1]} ondemand")
[[ "${PROVER_MARKET:-spot}" == ondemand ]] && TRIES=("${TYPES[0]} ondemand")
for TRY in "${TRIES[@]}"; do
  read -r TYPE MK <<< "$TRY"
  OPT=(); [[ "$MK" == spot ]] && OPT=(--instance-market-options \
    'MarketType=spot,SpotOptions={SpotInstanceType=one-time,InstanceInterruptionBehavior=terminate}')
  IIDS=$("${A[@]}" ec2 run-instances --image-id "$AMI" --instance-type "$TYPE" --count "$N" ${OPT[@]+"${OPT[@]}"} \
          --instance-initiated-shutdown-behavior terminate \
          --key-name "$AWS_KEY_NAME" --security-group-ids "$SG" --subnet-id "$SUBNET" \
          --block-device-mappings "DeviceName=/dev/sda1,Ebs={VolumeSize=30,VolumeType=gp3,DeleteOnTermination=true}" \
          --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=$NAME}]" \
          --query 'Instances[].InstanceId' --output text) && break
  echo "      no $MK $TYPE capacity"
done
[[ -n "$IIDS" ]] || exit 1
echo "      $MK $TYPE: $IIDS"
"${A[@]}" ec2 wait instance-status-ok --instance-ids $IIDS

echo "[3/5] bootstrap (liboqs, Rust STARK module, venv) in parallel"
KEY=$(head -c 24 /dev/urandom | base64)
ADDRS=(); READY=$(mktemp)
for IID in $IIDS; do
  read -r PUB PRIV < <("${A[@]}" ec2 describe-instances --instance-ids "$IID" \
       --query 'Reservations[0].Instances[0].[PublicIpAddress,PrivateIpAddress]' --output text)
  ADDRS+=("$PRIV:$PORT")
  (
    SSH=(ssh -n -i "$KEY_FILE" -o StrictHostKeyChecking=accept-new -o ConnectTimeout=5 "$AWS_SSH_USER@$PUB")
    for _ in $(seq 1 60); do "${SSH[@]}" true 2>/dev/null && break; sleep 3; done
    # hard cap before a bootstrap that could hang
    "${SSH[@]}" "sudo shutdown -h +${PROVER_HARD_CAP_MIN:-240} veredact-prover-hard-cap"
    scp -q -i "$KEY_FILE" -o StrictHostKeyChecking=accept-new deploy/server/bootstrap_server.sh "$AWS_SSH_USER@$PUB:/tmp/"
    "${SSH[@]}" "sudo mkdir -p $BENCH && sudo chown -R $AWS_SSH_USER $REPO_REMOTE_DIR"
    rsync -az -e "ssh -i $KEY_FILE -o StrictHostKeyChecking=accept-new" --exclude .git --exclude .venv \
      --exclude __pycache__ --exclude target --exclude '/results/*' --exclude .cache \
      --exclude 'deploy/aws/.*' --exclude deploy/besu/.network \
      ./ "$AWS_SSH_USER@$PUB:$BENCH/"
    "${SSH[@]}" "sudo QUICK=$QUICK REPO_URL=$REPO_URL REPO_BRANCH=$REPO_BRANCH REMOTE_DIR=$REPO_REMOTE_DIR bash /tmp/bootstrap_server.sh" \
      > "/tmp/veredact-prover-$IID.log" 2>&1
    # self-termination (shutdown = terminate): the hard cap above; idle 15 min after use; 45 min if never used
    "${SSH[@]}" "sudo cp $BENCH/deploy/server/prover_watchdog.sh /usr/local/bin/ \
      && echo '* * * * * root /usr/local/bin/prover_watchdog.sh $PORT' | sudo tee /etc/cron.d/veredact-prover >/dev/null"
    echo "[4/5] $IID: start prover service"
    # every stream of the background service is redirected, so ssh returns at once (macOS has no timeout(1))
    "${SSH[@]}" "cd $BENCH && VRPQ_PROVER_KEY='$KEY' VRPQ_SIG_BACKEND=oqs setsid nohup .venv/bin/python \
      scripts/prover_service.py --port $PORT > /tmp/prover.log 2>&1 < /dev/null &"
    for _ in $(seq 1 60); do "${SSH[@]}" "ss -Hltn sport = :$PORT | grep -q ." && break; sleep 5; done
    "${SSH[@]}" "ss -Hltn sport = :$PORT | grep -q ." && { echo "      $IID: listening on $PORT"; echo "$IID" >> "$READY"; } || echo "      $IID: PROVER SERVICE NOT LISTENING (/tmp/prover.log)"
  ) &
done
wait
if [[ $(wc -l < "$READY") -ne "$N" ]]; then   # never hand out a pool that is not fully up
  echo "      not every prover is listening: terminating $IIDS"; "${A[@]}" ec2 terminate-instances --instance-ids $IIDS >/dev/null; exit 1
fi
printf '%s\n%s\n' "$KEY" "$(IFS=,; echo "${ADDRS[*]}")" > deploy/aws/.provers
chmod 600 deploy/aws/.provers
echo "[5/5] provers: $(sed -n 2p deploy/aws/.provers)   (bootstrap logs: /tmp/veredact-prover-*.log)"
echo "      they stop themselves 15 min after use; early cleanup: [REGION=<region>] deploy/aws/teardown_provers.sh"
