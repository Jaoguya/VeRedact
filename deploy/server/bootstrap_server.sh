#!/usr/bin/env bash
# One-time setup of an Ubuntu 24.04 experiment server (run as root; provision_ec2.sh does this over SSH).
# Installs: Docker + compose, Python 3.12 venv, liboqs (ML-DSA-65, the paper's backend), tc/netem, Rust +
# maturin (builds the winterfell STARK module benchmark/pqzk_stark), clones the repo, creates
# benchmark/.venv and runs the unit + fidelity tests.
#
# Env: REPO_URL, REPO_BRANCH, REMOTE_DIR  (defaults below)
set -euo pipefail
REPO_URL=${REPO_URL:-https://github.com/Jaoguya/VeRedact.git}
REPO_BRANCH=${REPO_BRANCH:-main}
REMOTE_DIR=${REMOTE_DIR:-/opt/veredact}
LIBOQS_VERSION=0.16.0          # liboqs and liboqs-python are released in lockstep
RUN_USER=${SUDO_USER:-ubuntu}

export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y git curl rsync jq build-essential cmake ninja-build libssl-dev \
  python3.12 python3.12-venv python3.12-dev iproute2 docker.io docker-compose-v2
usermod -aG docker "$RUN_USER"
systemctl enable --now docker

# ---- liboqs (shared) + liboqs-python ------------------------------------------------------
if [[ "$(cat /usr/local/lib/liboqs.version 2>/dev/null)" != "$LIBOQS_VERSION" ]]; then
  tmp=$(mktemp -d)
  git clone --depth 1 --branch "$LIBOQS_VERSION" https://github.com/open-quantum-safe/liboqs.git "$tmp/liboqs"
  cmake -S "$tmp/liboqs" -B "$tmp/liboqs/build" -GNinja -DBUILD_SHARED_LIBS=ON -DOQS_BUILD_ONLY_LIB=ON \
        -DCMAKE_BUILD_TYPE=Release -DOQS_DIST_BUILD=ON
  cmake --build "$tmp/liboqs/build" && cmake --install "$tmp/liboqs/build"
  echo "$LIBOQS_VERSION" > /usr/local/lib/liboqs.version
  ldconfig
fi

# ---- repository + venv ----------------------------------------------------------------------
if [[ -d "$REMOTE_DIR/.git" ]]; then
  git -C "$REMOTE_DIR" pull --ff-only
elif [[ ! -f "$REMOTE_DIR/config/experiment.toml" ]]; then   # nothing synced from the laptop: clone
  git clone --branch "$REPO_BRANCH" "$REPO_URL" "$REMOTE_DIR"
fi
chown -R "$RUN_USER:$RUN_USER" "$REMOTE_DIR"
sudo -u "$RUN_USER" bash -lc "
  set -euo pipefail
  command -v cargo >/dev/null || curl -sSf https://sh.rustup.rs | sh -s -- -y --profile minimal
  source \$HOME/.cargo/env
  cd '$REMOTE_DIR/benchmark'
  python3.12 -m venv .venv
  .venv/bin/pip install -q -U pip maturin
  .venv/bin/pip install -q -r requirements.txt
  .venv/bin/pip install -q 'liboqs-python @ git+https://github.com/open-quantum-safe/liboqs-python@$LIBOQS_VERSION' web3 py-solc-x
  .venv/bin/pip install -q -e .
  (cd pqzk_stark && ../.venv/bin/maturin build --release -q -o target/wheels && ../.venv/bin/pip install -q --force-reinstall target/wheels/*.whl)
  VRPQ_SIG_BACKEND=oqs .venv/bin/python -c 'from veredact_bench.crypto.pqsig import load_pqsig; print(\"signature backend:\", load_pqsig(\"oqs\").name)'
  .venv/bin/python -m pytest -q tests ../experiment
"
echo "bootstrap complete: $REMOTE_DIR  (log out/in once so the docker group applies)"
