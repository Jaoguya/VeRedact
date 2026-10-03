"""Ledger backends every scheme anchors through (docs/experiments.md §1.3.1).

  besu        real Hyperledger Besu QBFT: every operation is a transaction to contracts/VeRedactRegistry.sol
              (VeRedact-PQ) or BaselineRedactionLog (baselines); ledger_ms = submit -> the block containing
              it is observed (one watcher polls every ledger.receipt_poll_ms, so thousands of in-flight
              transactions never queue behind a waiting thread), gas from the receipt. This is the only
              backend whose LedgerTime may be called consensus cost.
  in_process  in-memory log for smoke runs; LedgerTime is bookkeeping only (validate-config refuses it in
              the experiment tier).

submit() returns a Future resolving to (ledger_ms, gas_used): executors never block on a block period, so
Exp. 1 measures finality latency without serialising the pipeline behind it.
"""

import os
import threading
import time
from concurrent.futures import Future

from veredact_bench.utils.config import REPO_ROOT


class _Metered:
    """Every anchor keeps a receipt log [(op, ledger_ms, gas_used)] filled as receipts arrive, so Exp. 5
    reads gas for every system from the same place, whichever code path submitted the transaction."""

    def submit(self, op: str, **fields) -> Future:
        fut = self._submit(op, **fields)
        fut.add_done_callback(lambda f, op=op: f.exception() is None and self.receipts.append((op, *f.result())))
        return fut


def gather(futures: list) -> Future:
    """One Future for several anchoring transactions: (slowest ledger_ms, summed gas; None if any is None)."""
    out, left, res = Future(), [len(futures)], []
    lock = threading.Lock()
    if not futures:
        out.set_result((0.0, 0))
        return out

    def done(f):
        with lock:
            if out.done():
                return
            if f.exception() is not None:
                out.set_exception(f.exception())
                return
            res.append(f.result())
            left[0] -= 1
            if left[0] == 0:
                gas = [g for _, g in res]
                out.set_result((max(ms for ms, _ in res), None if None in gas else sum(gas)))

    for f in futures:
        f.add_done_callback(done)
    return out


class InProcessAnchor(_Metered):
    name = "in_process"

    def __init__(self, cfg=None):
        self.log, self.receipts = [], []

    def _submit(self, op: str, **fields) -> Future:
        t = time.perf_counter()
        self.log.append((op, fields))
        f = Future()
        f.set_result(((time.perf_counter() - t) * 1000, None))
        return f

    def close(self):
        pass


class BesuAnchor(_Metered):
    name = "besu"

    def __init__(self, cfg: dict):
        import solcx
        from web3 import Web3

        solcx.install_solc("0.8.24")
        src = REPO_ROOT / "contracts" / "VeRedactRegistry.sol"
        art = solcx.compile_files([str(src)], output_values=["abi", "bin"], solc_version="0.8.24", optimize=True)
        art = {k.split(":")[-1]: v for k, v in art.items()}
        self.w3 = Web3(Web3.HTTPProvider(cfg["ledger"]["rpc_url"]))
        key = os.environ.get("VRPQ_BESU_KEY")
        if not key:
            raise RuntimeError("VRPQ_BESU_KEY not set (funded dev key of the private Besu network)")
        led = cfg["ledger"]
        self.gas_limit, self.poll_s, self.timeout_s = (
            led["tx_gas_limit"],
            led["receipt_poll_ms"] / 1000,
            led["receipt_timeout_s"],
        )
        self.acct = self.w3.eth.account.from_key(key)
        self._nonce = self.w3.eth.get_transaction_count(self.acct.address)
        self._lock = threading.Lock()
        self.reg = self._deploy(art["VeRedactRegistry"])
        self.base = self._deploy(art["BaselineRedactionLog"])
        self.receipts = []
        self._ver = {}  # batch -> anchored version (contract enforces v_b' = v_b + 1)
        self._pending: dict[bytes, tuple] = {}  # tx hash -> (Future, submit time)
        self._mined: dict[bytes, float] = {}  # tx hash -> time its block was observed (for late registration)
        self._plock = threading.Lock()
        self._stop = threading.Event()
        self._last_block = self.w3.eth.block_number
        self._watcher = threading.Thread(target=self._watch, name="besu-block-watcher", daemon=True)
        self._watcher.start()

    # ---- transactions ---------------------------------------------------------------------------------
    def _send(self, fn):
        with self._lock:
            tx = fn.build_transaction(
                {"from": self.acct.address, "nonce": self._nonce, "gasPrice": 0, "gas": self.gas_limit}
            )
            self._nonce += 1
            return self.w3.eth.send_raw_transaction(self.acct.sign_transaction(tx).raw_transaction)

    def _deploy(self, art):
        c = self.w3.eth.contract(abi=art["abi"], bytecode=art["bin"])
        rcpt = self.w3.eth.wait_for_transaction_receipt(self._send(c.constructor()))
        return self.w3.eth.contract(address=rcpt.contractAddress, abi=art["abi"])

    def _watch(self):
        """Resolve every pending transaction when the block containing it is observed."""
        while not self._stop.is_set():
            head = self.w3.eth.block_number
            if head <= self._last_block:
                self._stop.wait(self.poll_s)
                continue
            seen = time.perf_counter()
            for bn in range(self._last_block + 1, head + 1):
                for h in self.w3.eth.get_block(bn).transactions:
                    h = bytes(h)
                    with self._plock:
                        item = self._pending.pop(h, None)
                        if item is None:
                            self._mined[h] = seen  # submitted but not yet registered: resolved on registration
                            continue
                    self._resolve(h, *item, seen)
            self._last_block = head
            with self._plock:  # forget unclaimed hashes after a while (deploys, other senders)
                for h in [h for h, t in self._mined.items() if seen - t > self.timeout_s]:
                    del self._mined[h]

    def _resolve(self, h, fut, t0, seen):
        rcpt = self.w3.eth.get_transaction_receipt(h)
        if rcpt.status != 1:
            fut.set_exception(RuntimeError(f"anchoring transaction reverted: {h.hex()}"))
        else:
            fut.set_result(((seen - t0) * 1000, rcpt.gasUsed))

    def _register(self, h, t0) -> Future:
        fut, h = Future(), bytes(h)
        with self._plock:
            seen = self._mined.pop(h, None)
            if seen is None:
                self._pending[h] = (fut, t0)
                return fut
        self._resolve(h, fut, t0, seen)
        return fut

    def _submit(self, op: str, **f) -> Future:
        t0 = time.perf_counter()
        r = os.urandom
        cp = lambda b, vb: (
            b.to_bytes(32, "big"),
            f.get("mr", r(32)),
            r(32),
            f.get("rli", r(32)),
            1,
            f.get("epoch", 1),
            vb,
            int(time.time()),
            b"\0" * 32,
        )
        if op == "policy_register":
            h = self._send(self.reg.functions.registerPolicy(f["pid"], f["commit"], 1, 0, f["sig"]))
        elif op == "committee_register":
            h = self._send(self.reg.functions.registerCommittee(f["epoch"], f["members"], f["n"], f["t"], f["sig"]))
        elif op == "batch_checkpoint":
            self._ver[f["b"]] = 0
            h = self._send(self.reg.functions.anchorCheckpoint(f["b"], cp(f["b"], 0), f["sig"]))
        elif op == "abrrr_authorization":
            h = self._send(self.reg.functions.anchorAuthorization(f["bid"], f["digest"]))
        elif op == "redaction_finalization":
            bs = f["batches"]
            cps = [cp(b, self._ver[b] + 1) for b in bs]
            for b in bs:
                self._ver[b] += 1
            h = self._send(self.reg.functions.finalizeRedaction(f["bid"], bs, cps, f["sigs"]))
        elif op == "rai_checkpoint":
            h = self._send(self.reg.functions.anchorRai(f["epoch"], f["cp"]))
        elif op == "baseline_redaction":
            h = self._send(self.base.functions.recordRedaction(f["tid"], f["commit"], f["version"], f["evidence"]))
        else:
            raise ValueError(f"unknown anchoring op {op}")
        return self._register(h, t0)

    def close(self):
        """Wait (up to ledger.receipt_timeout_s) for every submitted transaction, then stop the watcher."""
        deadline = time.perf_counter() + self.timeout_s
        while self._pending and time.perf_counter() < deadline:
            time.sleep(self.poll_s)
        self._stop.set()
        self._watcher.join()
        if self._pending:
            raise RuntimeError(f"{len(self._pending)} anchoring transactions not mined within {self.timeout_s} s")


def make_anchor(cfg: dict):
    return BesuAnchor(cfg) if cfg["ledger"]["backend"] == "besu" else InProcessAnchor(cfg)
