#!/usr/bin/env bash
# Run ON veredact-bench: launch requester prover hosts with the instance's IAM role (veredact-bench-role: may only
# launch/terminate instances tagged Name=veredact-prover; no AWS keys on the server), bootstrap them over the
# private network with the server's own key (~/.ssh/veredact-prover) and start scripts/prover_service.py.
#   deploy/server/provision_provers_local.sh [count=2] [instance_type=c7i.48xlarge]
# Writes deploy/aws/.provers (key, addresses) and deploy/aws/.prover_ids (for teardown_provers_local.sh).
set -euo pipefail
cd "$(dirname "$0")/../.."
eval "$(.venv/bin/python deploy/aws/aws_config.py)"
A=(aws --region "$AWS_REGION")      # the instance role, never a stored profile
N=${1:-2}; TYPE=${2:-c7i.48xlarge}; PORT=7700; NAME=veredact-prover
KEY_FILE="$HOME/.ssh/veredact-prover"
TOKEN=$(curl -fsS -X PUT http://169.254.169.254/latest/api/token -H "X-aws-ec2-metadata-token-ttl-seconds: 300")
SUBNET=$(curl -fsS -H "X-aws-ec2-metadata-token: $TOKEN" \
  "http://169.254.169.254/latest/meta-data/network/interfaces/macs/$(curl -fsS -H "X-aws-ec2-metadata-token: $TOKEN" \
  http://169.254.169.254/latest/meta-data/mac)/subnet-id")
SG=$("${A[@]}" ec2 describe-security-groups --filters "Name=group-name,Values=$NAME" --query 'SecurityGroups[0].GroupId' --output text)
[[ "$SG" == sg-* ]] || { echo "security group $NAME missing (deploy/aws/provision_provers.sh creates it once)"; exit 1; }
AMI=$("${A[@]}" ssm get-parameter --name "$AWS_AMI_SSM_PARAMETER" --query Parameter.Value --output text)

echo "[1/4] launch $N x $TYPE"
IIDS=$("${A[@]}" ec2 run-instances --image-id "$AMI" --instance-type "$TYPE" --count "$N" \
        --instance-initiated-shutdown-behavior terminate --key-name "$NAME" --security-group-ids "$SG" --subnet-id "$SUBNET" \
        --block-device-mappings "DeviceName=/dev/sda1,Ebs={VolumeSize=30,VolumeType=gp3,DeleteOnTermination=true}" \
        --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=$NAME}]" \
        --query 'Instances[].InstanceId' --output text)
echo "$IIDS" > deploy/aws/.prover_ids
echo "      $IIDS"
"${A[@]}" ec2 wait instance-status-ok --instance-ids $IIDS

echo "[2/4] bootstrap + self-termination + service (private network)"
KEY=$(head -c 24 /dev/urandom | base64)
ADDRS=()
for IID in $IIDS; do
  PRIV=$("${A[@]}" ec2 describe-instances --instance-ids "$IID" --query 'Reservations[0].Instances[0].PrivateIpAddress' --output text)
  ADDRS+=("$PRIV:$PORT")
  (
    SSH=(ssh -i "$KEY_FILE" -o StrictHostKeyChecking=accept-new -o ConnectTimeout=5 "$AWS_SSH_USER@$PRIV")
    for _ in $(seq 1 60); do "${SSH[@]}" true 2>/dev/null && break; sleep 3; done
    # self-termination first (shutdown = terminate): 4 h hard cap; 15 min idle after use; 45 min if never used
    "${SSH[@]}" "sudo shutdown -h +240 veredact-prover-hard-cap"
    scp -q -i "$KEY_FILE" -o StrictHostKeyChecking=accept-new deploy/server/bootstrap_server.sh "$AWS_SSH_USER@$PRIV:/tmp/"
    "${SSH[@]}" "sudo mkdir -p $REPO_REMOTE_DIR && sudo chown $AWS_SSH_USER $REPO_REMOTE_DIR"
    rsync -az -e "ssh -i $KEY_FILE -o StrictHostKeyChecking=accept-new" --exclude .git --exclude .venv \
      --exclude __pycache__ --exclude target --exclude '/results/*' --exclude '/paper/' --exclude .cache \
      --exclude deploy/aws/.instance --exclude deploy/aws/.provers --exclude deploy/aws/.prover_ids \
      --exclude deploy/besu/.network ./ "$AWS_SSH_USER@$PRIV:$REPO_REMOTE_DIR/"
    "${SSH[@]}" "sudo REPO_URL=$REPO_URL REPO_BRANCH=$REPO_BRANCH REMOTE_DIR=$REPO_REMOTE_DIR bash /tmp/bootstrap_server.sh" \
      > "results/logs/prover-bootstrap-$IID.log" 2>&1
    "${SSH[@]}" "sudo cp $REPO_REMOTE_DIR/deploy/server/prover_watchdog.sh /usr/local/bin/ \
      && echo '* * * * * root /usr/local/bin/prover_watchdog.sh $PORT' | sudo tee /etc/cron.d/veredact-prover >/dev/null"
    timeout 20 "${SSH[@]}" "cd $REPO_REMOTE_DIR && VRPQ_PROVER_KEY='$KEY' VRPQ_SIG_BACKEND=oqs setsid nohup .venv/bin/python \
      scripts/prover_service.py --port $PORT > /tmp/prover.log 2>&1 < /dev/null & sleep 3; tail -1 /tmp/prover.log" || true
  ) &
done
wait
printf '%s\n%s\n' "$KEY" "$(IFS=,; echo "${ADDRS[*]}")" > deploy/aws/.provers
chmod 600 deploy/aws/.provers
echo "[3/4] check every prover completes the authenticated handshake on $PORT (a bare TCP probe is not enough)"
for a in "${ADDRS[@]}"; do
  VRPQ_PROVER_KEY="$KEY" timeout 15 .venv/bin/python -c "import os,sys; from multiprocessing.connection import Client; \
Client((sys.argv[1], int(sys.argv[2])), authkey=os.environ['VRPQ_PROVER_KEY'].encode()).close()" "${a%:*}" "${a#*:}" \
    || { echo "prover $a not reachable"; exit 1; }
done
echo "[4/4] provers ready: $(sed -n 2p deploy/aws/.provers)"
