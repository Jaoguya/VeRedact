"""Ledger backends every scheme anchors through (docs/experiments.md §1.3.1).

  besu        real Hyperledger Besu QBFT: every operation is a transaction to contracts/VeRedactRegistry.sol
              (VeRedact-PQ) or BaselineRedactionLog (baselines); ledger_ms = submit -> receipt, gas from the
              receipt. This is the only backend whose LedgerTime may be called consensus cost.
  in_process  in-memory log for smoke runs; LedgerTime is bookkeeping only (validate-config refuses it in
              the experiment tier).

submit() returns a Future resolving to (ledger_ms, gas_used): executors never block on a block period, so
Exp. 1 measures finality latency without serialising the pipeline behind it.
"""
import os
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor

from .config import REPO_ROOT

SIG_BYTES = 3309  # ML-DSA-65 signature carried as calldata where the op anchors a PQ-signed object


class _Metered:
    """Every anchor keeps a receipt log [(op, ledger_ms, gas_used)] filled as receipts arrive, so Exp. 5
    reads gas for every system from the same place, whichever code path submitted the transaction."""

    def submit(self, op: str, **fields) -> Future:
        fut = self._submit(op, **fields)
        fut.add_done_callback(lambda f, op=op: f.exception() is None and self.receipts.append((op, *f.result())))
        return fut


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
        from web3 import Web3
        import solcx

        solcx.install_solc("0.8.24")
        src = REPO_ROOT / "benchmark" / "contracts" / "VeRedactRegistry.sol"
        art = solcx.compile_files([str(src)], output_values=["abi", "bin"], solc_version="0.8.24", optimize=True)
        art = {k.split(":")[-1]: v for k, v in art.items()}
        self.w3 = Web3(Web3.HTTPProvider(cfg["ledger"]["rpc_url"]))
        key = os.environ.get("VRPQ_BESU_KEY")
        if not key:
            raise RuntimeError("VRPQ_BESU_KEY not set (funded dev key of the private Besu network)")
        self.acct = self.w3.eth.account.from_key(key)
        self._nonce = self.w3.eth.get_transaction_count(self.acct.address)
        self._lock = threading.Lock()
        self.pool = ThreadPoolExecutor(max_workers=32)
        self.reg = self._deploy(art["VeRedactRegistry"])
        self.base = self._deploy(art["BaselineRedactionLog"])
        self.receipts = []
        self._ver = {}  # batch -> anchored version (contract enforces v_b' = v_b + 1)

    # ---- transactions ---------------------------------------------------------------------------------
    def _send(self, fn):
        with self._lock:
            tx = fn.build_transaction({"from": self.acct.address, "nonce": self._nonce, "gasPrice": 0,
                                       "gas": 30_000_000})
            self._nonce += 1
            return self.w3.eth.send_raw_transaction(self.acct.sign_transaction(tx).raw_transaction)

    def _deploy(self, art):
        c = self.w3.eth.contract(abi=art["abi"], bytecode=art["bin"])
        rcpt = self.w3.eth.wait_for_transaction_receipt(self._send(c.constructor()))
        return self.w3.eth.contract(address=rcpt.contractAddress, abi=art["abi"])

    def _wait(self, h, t0):
        rcpt = self.w3.eth.wait_for_transaction_receipt(h, timeout=600)
        if rcpt.status != 1:
            raise RuntimeError(f"anchoring transaction reverted: {h.hex()}")
        return (time.perf_counter() - t0) * 1000, rcpt.gasUsed

    def _submit(self, op: str, **f) -> Future:
        t0 = time.perf_counter()
        r = os.urandom
        cp = lambda b, vb: (b.to_bytes(32, "big"), f.get("mr", r(32)), r(32), f.get("rli", r(32)), 1,
                            f.get("epoch", 1), vb, int(time.time()), b"\0" * 32)
        if op == "policy_register":
            h = self._send(self.reg.functions.registerPolicy(f["pid"], f["commit"], 1, 0, r(SIG_BYTES)))
        elif op == "committee_register":
            h = self._send(self.reg.functions.registerCommittee(f["epoch"], f["members"], f["n"], f["t"], r(SIG_BYTES)))
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
        return self.pool.submit(self._wait, h, t0)

    def close(self):
        self.pool.shutdown(wait=True)


def make_anchor(cfg: dict):
    return BesuAnchor(cfg) if cfg["ledger"]["backend"] == "besu" else InProcessAnchor(cfg)
