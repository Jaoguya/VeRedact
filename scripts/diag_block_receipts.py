"""Diagnostic (full run 2026-10-09 hang): can eth_getBlockReceipts, called as soon as eth_blockNumber reports
a new block, return fewer receipts than the block holds? Sends self-transfers for --seconds while a poller
reads each new head immediately and compares len(receipts) with len(block.transactions).
Usage (server, Besu up, VRPQ_BESU_KEY set): scripts/diag_block_receipts.py --seconds 90"""

import argparse
import os
import threading
import time

from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=int, default=90)
    ap.add_argument("--rpc", default="http://127.0.0.1:8545")
    a = ap.parse_args()
    w3 = Web3(Web3.HTTPProvider(a.rpc))
    w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
    acct = w3.eth.account.from_key(os.environ["VRPQ_BESU_KEY"])
    stop = threading.Event()

    def send():
        nonce, cid = w3.eth.get_transaction_count(acct.address, "pending"), w3.eth.chain_id
        while not stop.is_set():
            tx = {"to": acct.address, "value": 0, "nonce": nonce, "gas": 21000, "gasPrice": 0, "chainId": cid}
            w3.eth.send_raw_transaction(acct.sign_transaction(tx).raw_transaction)
            nonce += 1
            time.sleep(0.01)

    threading.Thread(target=send, daemon=True).start()
    last, blocks, short = w3.eth.block_number, 0, []
    end = time.time() + a.seconds
    while time.time() < end:
        head = w3.eth.block_number
        for bn in range(last + 1, head + 1):
            r = w3.provider.make_request("eth_getBlockReceipts", [hex(bn)]).get("result")
            n_r = len(r) if r is not None else -1  # -1: null result
            n_t = len(w3.eth.get_block(bn)["transactions"])
            blocks += 1
            if n_r != n_t:
                short.append((bn, n_r, n_t, len(w3.provider.make_request("eth_getBlockReceipts", [hex(bn)])["result"])))
        last = head
        time.sleep(0.005)
    stop.set()
    print(f"blocks checked {blocks}; immediate receipts != block txs in {len(short)} blocks")
    for bn, n_r, n_t, later in short[:10]:
        print(f"  block {bn}: receipts at first read {n_r}, txs {n_t}, receipts on re-read {later}")


if __name__ == "__main__":
    main()
