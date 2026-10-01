#!/usr/bin/env bash
# Launch (or reuse) the experiment server described in config/aws.toml and bootstrap it.
#
# Usage:  deploy/aws/provision_ec2.sh            # launch + wait + copy this checkout + bootstrap
#         SYNC=git deploy/aws/provision_ec2.sh   # clone config/aws.toml [repo] from GitHub instead
#         DRY_RUN=1 deploy/aws/provision_ec2.sh  # print the AWS calls only
# Needs:  AWS CLI v2 with a working profile (aws sts get-caller-identity --profile <p> must succeed).
set -euo pipefail
cd "$(dirname "$0")/../.."
eval "$(python3 deploy/aws/aws_config.py)"
A=(aws --profile "$AWS_PROFILE" --region "$AWS_REGION")
run() { if [[ "${DRY_RUN:-0}" == 1 ]]; then echo "+ $*"; else "$@"; fi; }

echo "[1/6] credentials"
"${A[@]}" sts get-caller-identity --query Account --output text >/dev/null \
  || { echo "AWS credentials for profile '$AWS_PROFILE' are invalid. Run: aws configure --profile $AWS_PROFILE"; exit 1; }

echo "[2/6] key pair $AWS_KEY_NAME"
KEY_FILE="$HOME/.ssh/$AWS_KEY_NAME.pem"
if ! "${A[@]}" ec2 describe-key-pairs --key-names "$AWS_KEY_NAME" >/dev/null 2>&1; then
  if [[ "${DRY_RUN:-0}" == 1 ]]; then echo "+ create-key-pair $AWS_KEY_NAME -> $KEY_FILE"
  else
    "${A[@]}" ec2 create-key-pair --key-name "$AWS_KEY_NAME" --query KeyMaterial --output text > "$KEY_FILE"
    chmod 600 "$KEY_FILE"
  fi
fi

echo "[3/6] security group (SSH from your IP only)"
CIDR="$AWS_SSH_CIDR"
[[ "$CIDR" == auto ]] && CIDR="$(curl -fsS https://checkip.amazonaws.com)/32"
SG=$("${A[@]}" ec2 describe-security-groups --filters "Name=group-name,Values=$AWS_NAME_TAG" \
       --query 'SecurityGroups[0].GroupId' --output text 2>/dev/null || true)
if [[ -z "$SG" || "$SG" == None ]]; then
  SG=$(run "${A[@]}" ec2 create-security-group --group-name "$AWS_NAME_TAG" \
         --description "VeRedact benchmark SSH" --query GroupId --output text)
  run "${A[@]}" ec2 authorize-security-group-ingress --group-id "$SG" --protocol tcp --port 22 --cidr "$CIDR"
fi
[[ "${DRY_RUN:-0}" == 1 ]] || deploy/aws/refresh_ssh_rule.sh   # a reused group keeps an old IP otherwise

echo "[4/6] instance"
IID=$("${A[@]}" ec2 describe-instances \
       --filters "Name=tag:Name,Values=$AWS_NAME_TAG" "Name=instance-state-name,Values=pending,running,stopped" \
       --query 'Reservations[0].Instances[0].InstanceId' --output text 2>/dev/null || true)
if [[ -z "$IID" || "$IID" == None ]]; then
  AMI=$("${A[@]}" ssm get-parameter --name "$AWS_AMI_SSM_PARAMETER" --query Parameter.Value --output text)
  IID=$(run "${A[@]}" ec2 run-instances --image-id "$AMI" --instance-type "$AWS_INSTANCE_TYPE" \
          --key-name "$AWS_KEY_NAME" --security-group-ids "$SG" \
          --block-device-mappings "DeviceName=/dev/sda1,Ebs={VolumeSize=$AWS_VOLUME_GB,VolumeType=gp3}" \
          --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=$AWS_NAME_TAG}]" \
          --query 'Instances[0].InstanceId' --output text)
else
  run "${A[@]}" ec2 start-instances --instance-ids "$IID" >/dev/null || true
fi
[[ "${DRY_RUN:-0}" == 1 ]] && { echo "dry run: stop before waiting"; exit 0; }
"${A[@]}" ec2 wait instance-status-ok --instance-ids "$IID"
IP=$("${A[@]}" ec2 describe-instances --instance-ids "$IID" \
       --query 'Reservations[0].Instances[0].PublicIpAddress' --output text)
echo "$IID $IP" > deploy/aws/.instance   # read by the other scripts (gitignored)
echo "      $IID at $IP"

echo "[5/6] bootstrap (Docker, Python 3.12, liboqs, repo, venv) ~10 min"
SSH=(ssh -i "$KEY_FILE" -o StrictHostKeyChecking=accept-new "$AWS_SSH_USER@$IP")
scp -i "$KEY_FILE" -o StrictHostKeyChecking=accept-new deploy/server/bootstrap_server.sh "$AWS_SSH_USER@$IP:/tmp/"
if [[ "${SYNC:-local}" == local ]]; then   # default: ship this working tree (uncommitted changes included)
  "${SSH[@]}" "sudo mkdir -p $REPO_REMOTE_DIR && sudo chown $AWS_SSH_USER $REPO_REMOTE_DIR"
  rsync -az --delete -e "ssh -i $KEY_FILE -o StrictHostKeyChecking=accept-new" \
    --exclude .git --exclude .venv --exclude __pycache__ --exclude target --exclude '/results/*' --exclude '/plot/*' \
    --exclude deploy/aws/.instance --exclude deploy/besu/.network ./ "$AWS_SSH_USER@$IP:$REPO_REMOTE_DIR/"
fi                                           # SYNC=git: clone REPO_URL@REPO_BRANCH instead
"${SSH[@]}" "sudo REPO_URL=$REPO_URL REPO_BRANCH=$REPO_BRANCH REMOTE_DIR=$REPO_REMOTE_DIR bash /tmp/bootstrap_server.sh"

echo "[6/6] ready:  ssh -i $KEY_FILE $AWS_SSH_USER@$IP"
echo "      then:   deploy/aws/launch_run.sh <smoke|pilot|experiment> [exps]   (from this laptop)"
