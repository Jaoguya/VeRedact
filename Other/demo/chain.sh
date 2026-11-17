#!/usr/bin/env bash
# A small, real Hyperledger Besu QBFT chain for the live demo, in Docker on a laptop.
#   bash Other/demo/chain.sh up      start 4 validators (RPC on 127.0.0.1:8545), wait for blocks
#   bash Other/demo/chain.sh down    stop and remove them
# Adapted from Benchmark/deploy/besu/start_besu_network.sh (same image, genesis, chain id, dev account, tx pool).
# Smaller on purpose: 4 validators instead of 7 (the smallest QBFT network that still tolerates one faulty
# node), and no tc netem link delay (that needs a Linux host). Block period 2 s, as in the benchmark.
set -euo pipefail
cd "$(dirname "$0")"
export MSYS_NO_PATHCONV=1                      # Git Bash on Windows: pass container paths through unchanged
N=4
IMAGE=hyperledger/besu:25.6.0
CHAIN_ID=2026
BLOCK_S=2
DEV_ADDRESS=fe3b557e8fb62b89f4916b721be55ceb828dbd73  # public Besu dev key's address; private genesis only
NET=.chain                                     # generated (gitignored via .cache-style ignore below)
HOSTDIR=$(pwd -W 2>/dev/null || pwd)           # Docker Desktop on Windows wants a Windows path for -v
COMPOSE="$NET/docker-compose.yml"

if [[ "${1:-up}" == "down" ]]; then
  [[ -f "$COMPOSE" ]] && docker compose -f "$COMPOSE" down -v
  echo "demo chain stopped"
  exit 0
fi

[[ -f "$COMPOSE" ]] && docker compose -f "$COMPOSE" down -v >/dev/null 2>&1 || true
rm -rf "$NET" && mkdir -p "$NET"
cat > "$NET/qbftConfigFile.json" <<EOF
{
  "genesis": {
    "config": {
      "chainId": $CHAIN_ID, "berlinBlock": 0, "londonBlock": 0, "shanghaiTime": 0,
      "zeroBaseFee": true, "contractSizeLimit": 2147483647,
      "qbft": { "blockperiodseconds": $BLOCK_S, "epochlength": 30000, "requesttimeoutseconds": 4 }
    },
    "nonce": "0x0", "timestamp": "0x58ee40ba", "gasLimit": "0x1fffffffffffff", "difficulty": "0x1",
    "mixHash": "0x63746963616c2062797a616e74696e65206661756c7420746f6c6572616e6365",
    "coinbase": "0x0000000000000000000000000000000000000000",
    "alloc": { "$DEV_ADDRESS": { "balance": "0xad78ebc5ac6200000" } }
  },
  "blockchain": { "nodes": { "generate": true, "count": $N } }
}
EOF
# On a Windows bind mount Besu writes everything and then reports "Output directory already exists"; judge by
# the files it wrote, not by its exit code
docker run --rm -v "$HOSTDIR/$NET:/data" "$IMAGE" operator generate-blockchain-config \
  --config-file=/data/qbftConfigFile.json --to=/data/networkFiles --private-key-file-name=key >/dev/null 2>&1 || true
[[ -f "$NET/networkFiles/genesis.json" ]] || { echo "genesis generation failed" >&2; exit 1; }

KEYDIRS=()
for d in "$NET"/networkFiles/keys/*/; do KEYDIRS+=("$(basename "$d")"); done
BOOT_PUB=$(cut -c3- "$NET/networkFiles/keys/${KEYDIRS[0]}/key.pub")
{
  echo "name: veredact-demo-chain"
  echo "networks: { qbft: { ipam: { config: [ { subnet: 172.29.0.0/16 } ] } } }"
  echo "services:"
  for i in $(seq 1 "$N"); do
    ip="172.29.0.$((10 + i))"
    boot=""; [[ $i -gt 1 ]] && boot="--bootnodes=enode://$BOOT_PUB@172.29.0.11:30303"
    ports=""; [[ $i -eq 1 ]] && ports="    ports: [ \"127.0.0.1:8545:8545\" ]"
    cat <<EOF
  validator$i:
    image: $IMAGE
    container_name: demo-validator$i
    networks: { qbft: { ipv4_address: $ip } }
$ports
    volumes:
      - ./networkFiles/genesis.json:/config/genesis.json:ro
      - ./networkFiles/keys/${KEYDIRS[$((i - 1))]}:/config/keys:ro
    environment: { BESU_OPTS: "-Xmx512m" }
    command: >
      --genesis-file=/config/genesis.json --node-private-key-file=/config/keys/key
      --data-path=/tmp/data --p2p-host=$ip --p2p-port=30303 $boot
      --rpc-http-enabled --rpc-http-host=0.0.0.0 --rpc-http-api=ETH,NET,QBFT,WEB3,TXPOOL
      --host-allowlist=* --rpc-http-cors-origins=* --min-gas-price=0 --profile=ENTERPRISE
      --tx-pool=SEQUENCED --tx-pool-max-size=200000 --tx-pool-limit-by-account-percentage=1
EOF
  done
} > "$COMPOSE"
docker compose -f "$COMPOSE" up -d

for _ in $(seq 1 60); do
  h=$(curl -fsS -X POST -H 'content-type: application/json' \
       --data '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}' http://127.0.0.1:8545 2>/dev/null \
       | sed -n 's/.*"result":"\(0x[0-9a-f]*\)".*/\1/p' || true)
  if [[ -n "$h" ]] && (( h >= 2 )); then
    echo "demo chain up: $N Besu QBFT validators, block $((h)), RPC http://127.0.0.1:8545"
    exit 0
  fi
  sleep 2
done
echo "no blocks after 120 s; see: docker compose -f Other/demo/$COMPOSE logs" >&2
exit 1
