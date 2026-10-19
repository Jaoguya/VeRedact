#!/usr/bin/env bash
# Launch N worker servers for a repeated full run (one repetition each), identical to veredact-bench
# (configs/aws.toml instance type, AMI, volume, key, security group), tagged Name=veredact-rep-worker, and
# bootstrap them in parallel with this working tree. Writes deploy/aws/.workers ("rep instance-id ip" per line).
# Acts only on instances it launches. Usage: deploy/aws/provision_workers.sh <N>
set -euo pipefail
cd "$(dirname "$0")/../.."
N=${1:?usage: $0 <N>}
eval "$(.venv/bin/python deploy/aws/aws_config.py)"
A=(aws --profile "$AWS_PROFILE" --region "$AWS_REGION")
KEY="$HOME/.ssh/$AWS_KEY_NAME.pem"
NAME=veredact-rep-worker
SG=$("${A[@]}" ec2 describe-security-groups --filters "Name=group-name,Values=$AWS_NAME_TAG" --query 'SecurityGroups[0].GroupId' --output text)
deploy/aws/refresh_ssh_rule.sh >/dev/null
AMI=$("${A[@]}" ssm get-parameter --name "$AWS_AMI_SSM_PARAMETER" --query Parameter.Value --output text)
IIDS=$("${A[@]}" ec2 run-instances --image-id "$AMI" --instance-type "$AWS_INSTANCE_TYPE" --count "$N" \
        --key-name "$AWS_KEY_NAME" --security-group-ids "$SG" \
        --block-device-mappings "DeviceName=/dev/sda1,Ebs={VolumeSize=$AWS_VOLUME_GB,VolumeType=gp3}" \
        --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=$NAME}]" \
        --query 'Instances[].InstanceId' --output text)
echo "launched: $IIDS"
"${A[@]}" ec2 wait instance-status-ok --instance-ids $IIDS
: > deploy/aws/.workers
r=0
for IID in $IIDS; do
  r=$((r + 1))
  IP=$("${A[@]}" ec2 describe-instances --instance-ids "$IID" --query 'Reservations[0].Instances[0].PublicIpAddress' --output text)
  echo "$r $IID $IP" >> deploy/aws/.workers
done
mkdir -p results/logs
while read -r r IID IP; do
  (
    SSH=(ssh -i "$KEY" -o StrictHostKeyChecking=accept-new -o ConnectTimeout=10 "$AWS_SSH_USER@$IP")
    for _ in $(seq 1 60); do "${SSH[@]}" true 2>/dev/null && break; sleep 5; done
    scp -q -i "$KEY" -o StrictHostKeyChecking=accept-new deploy/server/bootstrap_server.sh "$AWS_SSH_USER@$IP:/tmp/"
    "${SSH[@]}" "sudo mkdir -p $REPO_REMOTE_DIR/Benchmark && sudo chown -R $AWS_SSH_USER $REPO_REMOTE_DIR"
    rsync -az -e "ssh -i $KEY -o StrictHostKeyChecking=accept-new" --exclude .git --exclude .venv --exclude __pycache__ \
      --exclude target --exclude '/results/*' --exclude .cache --exclude 'deploy/aws/.*' --exclude deploy/besu/.network \
      ./ "$AWS_SSH_USER@$IP:$REPO_REMOTE_DIR/Benchmark/"
    "${SSH[@]}" "sudo REPO_URL=$REPO_URL REPO_BRANCH=$REPO_BRANCH REMOTE_DIR=$REPO_REMOTE_DIR bash /tmp/bootstrap_server.sh" \
      > "results/logs/worker-bootstrap-$r.log" 2>&1 && echo "worker $r ($IP) bootstrapped" || echo "worker $r ($IP) BOOTSTRAP FAILED"
    "${SSH[@]}" "echo '* * * * * root $REPO_REMOTE_DIR/Benchmark/deploy/server/idle_watchdog.sh' | sudo tee /etc/cron.d/veredact-idle >/dev/null"
  ) &
done < deploy/aws/.workers
wait
cat deploy/aws/.workers
