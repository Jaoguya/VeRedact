#!/usr/bin/env bash
# Build the prebuilt machine image of a split run in the run region (configs/aws.toml [run] region): one on-demand
# builder from the Ubuntu image, full bootstrap of THIS working tree (tests included) + the Besu image pulled, then
# an AMI of it (Name=veredact-run-image). Workers and provers started from it only refresh the synced code
# (bootstrap QUICK=1): ~3 min instead of ~25. Refuses an uncommitted tree; writes deploy/aws/.image ("region ami
# snapshot commit"). teardown_workers.sh deletes the AMI and its snapshot after the full run (not after a smoke).
# Usage: deploy/aws/build_image.sh
set -euo pipefail
cd "$(dirname "$0")/../.."
eval "$(.venv/bin/python deploy/aws/aws_config.py)"
A=(aws --profile "$AWS_PROFILE" --region "$RUN_REGION")
KEY="$HOME/.ssh/$AWS_KEY_NAME.pem"
WF=deploy/aws/.image_builder
[[ -z "$(git status --porcelain -- .)" ]] || { echo "uncommitted changes in Benchmark/: commit first (the image is the run's code)"; exit 1; }
COMMIT=$(git rev-parse --short HEAD)
OK=0
cleanup() {   # a failed build never leaves the on-demand builder behind
  local id; read -r _ id _ < "$WF" 2>/dev/null || return 0
  (( OK )) || { "${A[@]}" ec2 terminate-instances --instance-ids "$id" >/dev/null && echo "builder $id terminated (build failed)"; }
  rm -f "$WF"
}
trap cleanup EXIT
WORKER_MARKET=ondemand WORKER_NAME=veredact-image-builder WORKERS_FILE=$WF NO_IMAGE=1 deploy/aws/provision_workers.sh 1
read -r _ IID IP < "$WF"
grep -q "bootstrapped" <(ssh -n -i "$KEY" -o StrictHostKeyChecking=accept-new "$AWS_SSH_USER@$IP" \
  "test -f $REPO_REMOTE_DIR/.on-server && echo bootstrapped") || { echo "builder bootstrap failed (results/logs/worker-bootstrap-1.log)"; exit 1; }
ssh -n -i "$KEY" "$AWS_SSH_USER@$IP" "sudo docker pull -q $BESU_IMAGE && sudo rm -f /etc/cron.d/veredact-idle /var/tmp/veredact-last-busy"
"${A[@]}" ec2 stop-instances --instance-ids "$IID" >/dev/null
"${A[@]}" ec2 wait instance-stopped --instance-ids "$IID"
AMI=$("${A[@]}" ec2 create-image --instance-id "$IID" --name "veredact-run-image-$(date -u +%Y%m%d-%H%M%S)" \
        --tag-specifications "ResourceType=image,Tags=[{Key=Name,Value=veredact-run-image}]" \
        "ResourceType=snapshot,Tags=[{Key=Name,Value=veredact-run-image}]" --query ImageId --output text)
"${A[@]}" ec2 wait image-available --image-ids "$AMI"
SNAP=$("${A[@]}" ec2 describe-images --image-ids "$AMI" --query 'Images[0].BlockDeviceMappings[0].Ebs.SnapshotId' --output text)
read -r OREG OAMI OSNAP _ 2>/dev/null < deploy/aws/.image || true   # the image this one replaces goes
if [[ "${OREG:-}" == "$RUN_REGION" && -n "${OAMI:-}" && "$OAMI" != "$AMI" ]]; then
  "${A[@]}" ec2 deregister-image --image-id "$OAMI" && "${A[@]}" ec2 delete-snapshot --snapshot-id "$OSNAP" && echo "old image $OAMI deleted"
fi
echo "$RUN_REGION $AMI $SNAP $COMMIT" > deploy/aws/.image
"${A[@]}" ec2 terminate-instances --instance-ids "$IID" >/dev/null
OK=1
echo "image $AMI (snapshot $SNAP, commit $COMMIT) in $RUN_REGION; builder $IID terminated"
