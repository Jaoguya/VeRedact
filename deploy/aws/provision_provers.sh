#!/usr/bin/env bash
# Launch requester prover hosts for Exp. 1 (audit A4) next to veredact-bench, bootstrap them and start
# scripts/prover_service.py. Only instances tagged Name=veredact-prover are created; terminate them right after
# Exp. 1 with deploy/aws/teardown_provers.sh (they are large and cost money every hour).
#   deploy/aws/provision_provers.sh [count=2] [instance_type=c7i.48xlarge]
# Writes deploy/aws/.provers (gitignored): line 1 = VRPQ_PROVER_KEY, line 2 = VRPQ_PROVERS (private ip:7700,...).
set -euo pipefail
cd "$(dirname "$0")/../.."
eval "$(.venv/bin/python deploy/aws/aws_config.py 2>/dev/null || python3 deploy/aws/aws_config.py)"
A=(aws --profile "$AWS_PROFILE" --region "$AWS_REGION")
N=${1:-2}; TYPE=${2:-c7i.48xlarge}; PORT=7700; NAME=veredact-prover
KEY_FILE="$HOME/.ssh/$AWS_KEY_NAME.pem"
read -r SYS_IID _ < deploy/aws/.instance
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

echo "[2/5] launch $N x $TYPE (same subnet as veredact-bench)"
AMI=$("${A[@]}" ssm get-parameter --name "$AWS_AMI_SSM_PARAMETER" --query Parameter.Value --output text)
IIDS=$("${A[@]}" ec2 run-instances --image-id "$AMI" --instance-type "$TYPE" --count "$N" \
        --instance-initiated-shutdown-behavior terminate \
        --key-name "$AWS_KEY_NAME" --security-group-ids "$SG" --subnet-id "$SUBNET" \
        --block-device-mappings "DeviceName=/dev/sda1,Ebs={VolumeSize=30,VolumeType=gp3,DeleteOnTermination=true}" \
        --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=$NAME}]" \
        --query 'Instances[].InstanceId' --output text)
echo "      $IIDS"
"${A[@]}" ec2 wait instance-status-ok --instance-ids $IIDS

echo "[3/5] bootstrap (liboqs, Rust STARK module, venv) in parallel"
KEY=$(head -c 24 /dev/urandom | base64)
ADDRS=()
for IID in $IIDS; do
  read -r PUB PRIV < <("${A[@]}" ec2 describe-instances --instance-ids "$IID" \
       --query 'Reservations[0].Instances[0].[PublicIpAddress,PrivateIpAddress]' --output text)
  ADDRS+=("$PRIV:$PORT")
  (
    SSH=(ssh -i "$KEY_FILE" -o StrictHostKeyChecking=accept-new "$AWS_SSH_USER@$PUB")
    for _ in $(seq 1 60); do "${SSH[@]}" -o ConnectTimeout=3 true 2>/dev/null && break; sleep 3; done
    scp -q -i "$KEY_FILE" -o StrictHostKeyChecking=accept-new deploy/server/bootstrap_server.sh "$AWS_SSH_USER@$PUB:/tmp/"
    "${SSH[@]}" "sudo mkdir -p $REPO_REMOTE_DIR && sudo chown $AWS_SSH_USER $REPO_REMOTE_DIR"
    rsync -az -e "ssh -i $KEY_FILE -o StrictHostKeyChecking=accept-new" --exclude .git --exclude .venv \
      --exclude __pycache__ --exclude target --exclude '/results/*' --exclude '/paper/' --exclude .cache \
      --exclude deploy/aws/.instance --exclude deploy/aws/.provers --exclude deploy/besu/.network \
      ./ "$AWS_SSH_USER@$PUB:$REPO_REMOTE_DIR/"
    "${SSH[@]}" "sudo REPO_URL=$REPO_URL REPO_BRANCH=$REPO_BRANCH REMOTE_DIR=$REPO_REMOTE_DIR bash /tmp/bootstrap_server.sh" \
      > "/tmp/veredact-prover-$IID.log" 2>&1
    # self-termination FIRST (shutdown = terminate): hard cap 4 h; idle 15 min after a run used it; 45 min if
    # never used — set before anything that could hang or fail (2026-10-08: it was skipped once)
    "${SSH[@]}" "sudo shutdown -h +240 veredact-prover-hard-cap; sudo cp $REPO_REMOTE_DIR/deploy/server/prover_watchdog.sh /usr/local/bin/ \
      && echo '* * * * * root /usr/local/bin/prover_watchdog.sh $PORT' | sudo tee /etc/cron.d/veredact-prover >/dev/null"
    echo "[4/5] $IID: start prover service"
    # the backgrounded service keeps the ssh channel open: bounded by timeout, and its exit status ignored
    timeout 20 "${SSH[@]}" "cd $REPO_REMOTE_DIR && VRPQ_PROVER_KEY='$KEY' VRPQ_SIG_BACKEND=oqs setsid nohup .venv/bin/python \
      scripts/prover_service.py --port $PORT > /tmp/prover.log 2>&1 < /dev/null & sleep 3; tail -1 /tmp/prover.log" || true
  ) &
done
wait
printf '%s\n%s\n' "$KEY" "$(IFS=,; echo "${ADDRS[*]}")" > deploy/aws/.provers
chmod 600 deploy/aws/.provers
echo "[5/5] provers: $(sed -n 2p deploy/aws/.provers)   (bootstrap logs: /tmp/veredact-prover-*.log)"
echo "      run:  deploy/aws/launch_run.sh experiment exp01_redaction_throughput   (picks up deploy/aws/.provers)"
echo "      then: deploy/aws/teardown_provers.sh"
