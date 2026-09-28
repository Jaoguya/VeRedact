"""Measure Exp. 5 gas on a running Hyperledger Besu (QBFT) network from transaction receipts.

Replays the on-chain operation log produced by the harness (python -m veredact_bench exp5 writes
results/exp5_chainlog.json) against contracts/VeRedactRegistry.sol and BaselineRedactionLog.

Prerequisites (not installed by default):
    pip install web3 py-solc-x
    a Besu QBFT network with an unlocked/funded account, e.g.
      besu operator generate-blockchain-config --config-file=qbft.json --to=network --private-key-file-name=key
      (gas price 0 in the permissioned deployment; gas usage is still reported in receipts)

Usage:
    python scripts/measure_gas_besu.py --rpc http://127.0.0.1:8545 --key 0x<private key> \
        --log results/exp5_chainlog.json --out results/exp5_gas_besu.csv
"""
import argparse
import csv
import json
import os

SIG_BYTES = 3309  # ML-DSA-65


def compile_contracts(path):
    import solcx

    solcx.install_solc("0.8.24")
    out = solcx.compile_files([path], output_values=["abi", "bin"], solc_version="0.8.24", optimize=True)
    return {k.split(":")[-1]: v for k, v in out.items()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rpc", default="http://127.0.0.1:8545")
    ap.add_argument("--key", required=True)
    ap.add_argument("--log", default="results/exp5_chainlog.json")
    ap.add_argument("--out", default="results/exp5_gas_besu.csv")
    a = ap.parse_args()

    from web3 import Web3

    w3 = Web3(Web3.HTTPProvider(a.rpc))
    acct = w3.eth.account.from_key(a.key)
    art = compile_contracts(os.path.join(os.path.dirname(__file__), "..", "contracts", "VeRedactRegistry.sol"))

    def send(fn):
        tx = fn.build_transaction({"from": acct.address, "nonce": w3.eth.get_transaction_count(acct.address),
                                   "gasPrice": 0, "gas": 30_000_000})
        rcpt = w3.eth.wait_for_transaction_receipt(w3.eth.send_raw_transaction(acct.sign_transaction(tx).raw_transaction))
        return rcpt.gasUsed

    def deploy(name):
        c = w3.eth.contract(abi=art[name]["abi"], bytecode=art[name]["bin"])
        tx = c.constructor().build_transaction({"from": acct.address, "nonce": w3.eth.get_transaction_count(acct.address),
                                                "gasPrice": 0, "gas": 30_000_000})
        rcpt = w3.eth.wait_for_transaction_receipt(w3.eth.send_raw_transaction(acct.sign_transaction(tx).raw_transaction))
        return w3.eth.contract(address=rcpt.contractAddress, abi=art[name]["abi"])

    reg, base = deploy("VeRedactRegistry"), deploy("BaselineRedactionLog")
    rnd = lambda n=32: os.urandom(n)
    # chDigest is fixed per batch: finalizeRedaction requires CH_b to be preserved
    cp = lambda b, vb: (b.to_bytes(32, "big"), rnd(), rnd(), rnd(), 1, 1, vb, 1, b"\0" * 32)
    rows, next_b, bid_i, ver = [], 0, 0, {}
    for run in json.load(open(a.log)):
        for op in run["ops"]:
            kind = op["op"]
            if kind == "policy_register":
                g = send(reg.functions.registerPolicy(rnd(), rnd(), 1, 0, rnd(SIG_BYTES)))
            elif kind == "committee_register":
                g = send(reg.functions.registerCommittee(run.get("epoch", 1), rnd(), 7, 5, rnd(SIG_BYTES)))
            elif kind == "batch_checkpoint":
                g = send(reg.functions.anchorCheckpoint(next_b, cp(next_b, 0), rnd(SIG_BYTES)))
                ver[next_b] = 0
                next_b += 1
            elif kind == "abrrr_authorization":
                bid_i += 1
                g = send(reg.functions.anchorAuthorization(bid_i.to_bytes(32, "big"), rnd()))
            elif kind == "redaction_finalization":
                k = op.get("transitions", 1)
                bs = list(ver)[:k]  # transitions land on distinct anchored batches; versions advance by 1
                cps = [cp(b, ver[b] + 1) for b in bs]
                g = send(reg.functions.finalizeRedaction(bid_i.to_bytes(32, "big"), bs, cps, [rnd(SIG_BYTES)] * len(bs)))
                for b in bs:
                    ver[b] += 1
            elif kind == "rai_checkpoint":
                g = send(reg.functions.anchorRai(1, rnd()))
            elif kind == "per_request_redaction":  # baselines anchor per request
                g = send(base.functions.recordRedaction(rnd(), rnd(), 1, rnd(op["bytes"] - 32)))
            else:
                continue
            rows.append({"run": run["label"], "op": kind, "gas": g, **{k: v for k, v in op.items() if k != "op"}})
    with open(a.out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=sorted({k for r in rows for k in r}))
        w.writeheader()
        w.writerows(rows)
    print(f"-> {a.out} ({len(rows)} receipts)")


if __name__ == "__main__":
    main()
