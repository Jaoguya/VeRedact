#!/usr/bin/env bash
# Stop and remove the local Besu QBFT network started by start_besu_network.sh.
set -euo pipefail
cd "$(dirname "$0")/../.."
COMPOSE=deploy/besu/.network/docker-compose.besu.yml
[[ -f "$COMPOSE" ]] && docker compose -f "$COMPOSE" down -v
echo "Besu network stopped"
