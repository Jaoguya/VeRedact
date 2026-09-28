#!/usr/bin/env bash
# Start a local Hyperledger Besu QBFT network in Docker (manuscript: Besu + QBFT, Solidity anchoring).
#   - N validators (config/aws.toml [besu].validators), block period, chain id, funded dev account
#   - inter-node latency with tc netem on each container's host-side veth ([besu].netem_delay_ms)
#   - JSON-RPC of validator 1 on localhost:[besu].rpc_port
# Usage: deploy/besu/start_besu_network.sh          (Linux host with Docker; run on the AWS server)
#        deploy/besu/stop_besu_network.sh
set -euo pipefail
cd "$(dirname "$0")/../.."
eval "$(python3 deploy/aws/aws_config.py)"
NET=deploy/besu/.network          # generated, gitignored
N=$BESU_VALIDATORS
rm -rf "$NET" && mkdir -p "$NET"

# ---- 1. genesis + validator keys (besu operator generate-blockchain-config) ---------------------
cat > "$NET/qbftConfigFile.json" <<EOF
{
  "genesis": {
    "config": {
      "chainId": $BESU_CHAIN_ID, "berlinBlock": 0, "londonBlock": 0, "shanghaiTime": 0,
      "zeroBaseFee": true, "contractSizeLimit": 2147483647,
      "qbft": { "blockperiodseconds": $BESU_BLOCK_PERIOD_S, "epochlength": 30000, "requesttimeoutseconds": 4 }
    },
    "nonce": "0x0", "timestamp": "0x58ee40ba", "gasLimit": "0x1fffffffffffff", "difficulty": "0x1",
    "mixHash": "0x63746963616c2062797a616e74696e65206661756c7420746f6c6572616e6365",
    "coinbase": "0x0000000000000000000000000000000000000000",
    "alloc": { "${BESU_DEV_ADDRESS#0x}": { "balance": "0xad78ebc5ac6200000" } }
  },
  "blockchain": { "nodes": { "generate": true, "count": $N } }
}
EOF
docker run --rm -u "$(id -u):$(id -g)" -v "$PWD/$NET:/data" "$BESU_IMAGE" \
  operator generate-blockchain-config --config-file=/data/qbftConfigFile.json \
  --to=/data/networkFiles --private-key-file-name=key >/dev/null

# ---- 2. docker compose: validator 1 is the bootnode --------------------------------------------
mapfile -t KEYDIRS < <(ls -d "$NET"/networkFiles/keys/*/ | sort)
BOOT_PUB=$(cut -c3- "${KEYDIRS[0]}key.pub")
COMPOSE="$NET/docker-compose.besu.yml"
{
  echo "name: veredact-besu"
  echo "networks: { qbft: { ipam: { config: [ { subnet: 172.28.0.0/16 } ] } } }"
  echo "services:"
  for i in $(seq 1 "$N"); do
    ip="172.28.0.$((10 + i))"
    boot=""
    [[ $i -gt 1 ]] && boot="--bootnodes=enode://$BOOT_PUB@172.28.0.11:30303"
    ports=""
    [[ $i -eq 1 ]] && ports="    ports: [ \"127.0.0.1:$BESU_RPC_PORT:8545\" ]"
    cat <<EOF
  validator$i:
    image: $BESU_IMAGE
    container_name: besu-validator$i
    networks: { qbft: { ipv4_address: $ip } }
$ports
    volumes:
      - ../../../$NET/networkFiles/genesis.json:/config/genesis.json:ro
      - ../../../${KEYDIRS[$((i - 1))]%/}:/config/keys:ro
    command: >
      --genesis-file=/config/genesis.json --node-private-key-file=/config/keys/key
      --data-path=/tmp/data --p2p-host=$ip --p2p-port=30303 $boot
      --rpc-http-enabled --rpc-http-host=0.0.0.0 --rpc-http-api=ETH,NET,QBFT,WEB3,TXPOOL
      --host-allowlist=* --rpc-http-cors-origins=* --min-gas-price=0 --profile=ENTERPRISE
EOF
  done
} > "$COMPOSE"
docker compose -f "$COMPOSE" up -d

# ---- 3. tc netem on each validator's host-side veth --------------------------------------------
if [[ "${BESU_NETEM_DELAY_MS}" != 0 ]]; then
  sleep 3
  for i in $(seq 1 "$N"); do
    idx=$(docker exec "besu-validator$i" cat /sys/class/net/eth0/iflink)
    veth=$(ip -o link | awk -F': ' -v i="$idx" '$1==i {print $2}' | cut -d@ -f1)
    sudo tc qdisc replace dev "$veth" root netem delay "${BESU_NETEM_DELAY_MS}ms"
  done
  echo "netem: ${BESU_NETEM_DELAY_MS} ms on $N validator links"
fi

# ---- 4. wait for block production ----------------------------------------------------------------
for _ in $(seq 1 60); do
  h=$(curl -fsS -X POST -H 'content-type: application/json' \
       --data '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}' \
       "http://127.0.0.1:$BESU_RPC_PORT" 2>/dev/null | jq -r .result || true)
  if [[ -n "$h" && "$h" != null && $((h)) -ge 2 ]]; then
    echo "Besu QBFT up: $N validators, block $((h)), RPC http://127.0.0.1:$BESU_RPC_PORT"
    exit 0
  fi
  sleep 2
done
echo "Besu did not produce blocks in 120 s; see: docker compose -f $COMPOSE logs" >&2
exit 1
