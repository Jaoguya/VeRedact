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
from concurrent.futures import Future, ThreadPoolExecutor

from veredact_bench.utils.config import REPO_ROOT
from veredact_bench.utils.log import get_logger

log = get_logger()


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
        from web3.middleware import ExtraDataToPOAMiddleware

        solcx.install_solc("0.8.24")
        src = REPO_ROOT / "contracts" / "VeRedactRegistry.sol"
        art = solcx.compile_files([str(src)], output_values=["abi", "bin"], solc_version="0.8.24", optimize=True)
        art = {k.split(":")[-1]: v for k, v in art.items()}
        self.w3 = Web3(Web3.HTTPProvider(cfg["ledger"]["rpc_url"]))
        # QBFT blocks carry the validator set and seals in extraData (> 32 bytes): without this middleware
        # every get_block() raises ExtraDataLengthError and the block watcher dies
        self.w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
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
        self._nonce = self._drained_nonce()
        self._chain_id = self.w3.eth.chain_id  # fixed: building a transaction never asks the node for it again
        self._lock = threading.Lock()
        self._senders = ThreadPoolExecutor(led["sender_threads"], thread_name_prefix="besu-sender")
        self.reg = self._deploy(art["VeRedactRegistry"])
        self.base = self._deploy(art["BaselineRedactionLog"])
        self.receipts = []
        self._ver = {}  # batch -> anchored version (contract enforces v_b' = v_b + 1)
        self._pending: dict[bytes, tuple] = {}  # tx hash -> (Future, submit time)
        self._raw: dict[bytes, bytes] = {}  # tx hash -> signed raw transaction (re-sent if the node lost it)
        self.recheck_s = 30.0  # [METHOD] a transaction pending this long is looked up directly (see _recheck)
        self.recovered = {"late_receipt": 0, "resent": 0, "timed_out": 0}
        self._mined: dict[bytes, float] = {}  # tx hash -> time its block was observed (for late registration)
        self._plock = threading.Lock()
        self._stop = threading.Event()
        self._last_block = self.w3.eth.block_number
        self._watcher = threading.Thread(target=self._watch, name="besu-block-watcher", daemon=True)
        self._watcher.start()

    def _drained_nonce(self) -> int:
        """Wait until the previous point's transactions (e.g. a saturated rate) are mined, so this point
        neither reuses their nonces ('Nonce too low') nor competes with their backlog for block space."""
        addr, deadline = self.acct.address, time.perf_counter() + self.timeout_s
        while (n := self.w3.eth.get_transaction_count(addr, "pending")) != self.w3.eth.get_transaction_count(addr):
            if time.perf_counter() > deadline:
                raise RuntimeError(f"previous transactions of {addr} not mined within {self.timeout_s} s")
            time.sleep(self.poll_s)
        return n

    # ---- transactions ---------------------------------------------------------------------------------
    def _sign(self, fn):
        """Assign the next nonce and sign, in submission order (local, ~0.5 ms)."""
        with self._lock:
            tx = fn.build_transaction(
                {
                    "from": self.acct.address,
                    "nonce": self._nonce,
                    "gasPrice": 0,
                    "gas": self.gas_limit,
                    "chainId": self._chain_id,
                }
            )
            self._nonce += 1
            return self.acct.sign_transaction(tx)

    def _send(self, fn, t0: float) -> Future:
        """Sign in order, register, then send concurrently: the ~12 ms RPC runs on a sender thread, so the
        caller never waits for it and nonces may reach the node out of order (Besu's pool holds the gap
        until it is filled). Registered before sending, so a failed send always resolves its Future."""
        stx = self._sign(fn)
        h = bytes(stx.hash)
        self._raw[h] = bytes(stx.raw_transaction)
        fut = self._register(h, t0)
        self._senders.submit(self.w3.eth.send_raw_transaction, stx.raw_transaction).add_done_callback(
            lambda f: f.exception() is not None and self._fail(h, f.exception())
        )
        return fut

    def _fail(self, h: bytes, e: BaseException):
        with self._plock:
            item = self._pending.pop(h, None)
        self._raw.pop(h, None)
        if item is not None:
            item[0].set_exception(e)

    def _deploy(self, art):
        c = self.w3.eth.contract(abi=art["abi"], bytecode=art["bin"])
        stx = self._sign(c.constructor())
        self.w3.eth.send_raw_transaction(stx.raw_transaction)
        rcpt = self.w3.eth.wait_for_transaction_receipt(stx.hash)
        return self.w3.eth.contract(address=rcpt.contractAddress, abi=art["abi"])

    def _block_receipts(self, bn: int) -> list[tuple[bytes, bool, int]]:
        """(tx hash, succeeded, gasUsed) of every transaction in block bn: ONE eth_getBlockReceipts call per
        block. One eth_getTransactionReceipt per transaction (~12 ms each, serial) fell behind above ~80 tx/s
        and delayed when later blocks were seen, inflating every system's finality time (pilot 2026-10-04)."""
        rs = self.w3.provider.make_request("eth_getBlockReceipts", [hex(bn)])["result"]
        return [(bytes.fromhex(r["transactionHash"][2:]), int(r["status"], 16) == 1, int(r["gasUsed"], 16)) for r in rs]

    def _watch(self):
        """Resolve every pending transaction when the block containing it is observed."""
        while not self._stop.is_set():
            head = self.w3.eth.block_number
            self._recheck()
            if head <= self._last_block:
                self._stop.wait(self.poll_s)
                continue
            seen = time.perf_counter()
            for bn in range(self._last_block + 1, head + 1):
                for h, ok, gas in self._block_receipts(bn):
                    with self._plock:
                        item = self._pending.pop(h, None)
                        if item is None:  # submitted but not yet registered: resolved on registration
                            self._mined[h] = (seen, ok, gas)
                            continue
                    self._resolve_and_forget(h, *item, seen, ok, gas)
            self._last_block = head
            with self._plock:  # forget unclaimed hashes after a while (deploys, other senders)
                for h in [h for h, m in self._mined.items() if seen - m[0] > self.timeout_s]:
                    del self._mined[h]

    def _recheck(self):
        """Full run 2026-10-09: a Future of a MINED transaction (account nonce latest == pending) was never
        resolved and the harness waited 3.5 h. The block-receipt path missed it (cause not reproduced:
        scripts/diag_block_receipts.py). Safety net, so no Future can wait forever: a transaction pending
        > recheck_s is looked up by hash; a receipt resolves it (late_receipt), an unknown transaction is sent
        again (resent), and one pending > receipt_timeout_s fails its Future (timed_out). Counts are logged."""
        now = time.perf_counter()
        with self._plock:
            old = [(h, item) for h, item in self._pending.items() if now - item[1] > self.recheck_s]
        for h, (fut, t0) in old:
            try:
                r = self.w3.eth.get_transaction_receipt(h)
            except Exception:  # web3 TransactionNotFound: not mined (yet)
                r = None
            if r is not None:
                with self._plock:
                    if self._pending.pop(h, None) is None:
                        continue
                self.recovered["late_receipt"] += 1
                log.warning(f"anchor: receipt found by hash for {h.hex()[:16]} (missed by the block watcher)")
                self._resolve_and_forget(h, fut, t0, time.perf_counter(), r["status"] == 1, r["gasUsed"])
            elif now - t0 > self.timeout_s:
                self.recovered["timed_out"] += 1
                self._fail(h, RuntimeError(f"anchoring transaction {h.hex()} not mined within {self.timeout_s} s"))
            elif self._raw.get(h) is not None:
                try:
                    known = self.w3.eth.get_transaction(h) is not None
                except Exception:
                    known = False
                if not known:  # sent at most once more; afterwards only the receipt or the timeout ends it
                    raw = self._raw.pop(h, None)
                    self.recovered["resent"] += 1
                    log.warning(f"anchor: node does not know {h.hex()[:16]}; sending it again")
                    try:
                        self.w3.eth.send_raw_transaction(raw)
                    except Exception as e:  # e.g. nonce too low: it was mined after all; the receipt resolves it
                        log.warning(f"anchor: re-send of {h.hex()[:16]} failed: {e}")

    def _resolve_and_forget(self, h, fut, t0, seen, ok, gas):
        self._raw.pop(h, None)
        self._resolve(h, fut, t0, seen, ok, gas)

    @staticmethod
    def _resolve(h, fut, t0, seen, ok, gas):
        if not ok:
            fut.set_exception(RuntimeError(f"anchoring transaction reverted: {h.hex()}"))
        else:
            fut.set_result(((seen - t0) * 1000, gas))

    def _register(self, h, t0) -> Future:
        fut, h = Future(), bytes(h)
        with self._plock:
            mined = self._mined.pop(h, None)
            if mined is None:
                self._pending[h] = (fut, t0)
                return fut
        self._resolve_and_forget(h, fut, t0, *mined)
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
            h = self._send(self.reg.functions.registerPolicy(f["pid"], f["commit"], 1, 0, f["sig"]), t0)
        elif op == "committee_register":
            h = self._send(self.reg.functions.registerCommittee(f["epoch"], f["members"], f["n"], f["t"], f["sig"]), t0)
        elif op == "batch_checkpoint":
            self._ver[f["b"]] = 0
            h = self._send(self.reg.functions.anchorCheckpoint(f["b"], cp(f["b"], 0), f["sig"]), t0)
        elif op == "abrrr_authorization":
            h = self._send(self.reg.functions.anchorAuthorization(f["bid"], f["digest"]), t0)
        elif op == "redaction_finalization":
            bs = f["batches"]
            cps = [cp(b, self._ver[b] + 1) for b in bs]
            for b in bs:
                self._ver[b] += 1
            h = self._send(self.reg.functions.finalizeRedaction(f["bid"], bs, cps, f["sigs"]), t0)
        elif op == "rai_checkpoint":
            h = self._send(self.reg.functions.anchorRai(f["epoch"], f["cp"]), t0)
        elif op == "baseline_redaction":
            h = self._send(self.base.functions.recordRedaction(f["tid"], f["commit"], f["version"], f["evidence"]), t0)
        else:
            raise ValueError(f"unknown anchoring op {op}")
        return h

    def close(self):
        """Wait (up to ledger.receipt_timeout_s) for every submitted transaction, then stop the watcher."""
        deadline = time.perf_counter() + self.timeout_s
        while self._pending and time.perf_counter() < deadline:
            time.sleep(self.poll_s)
        self._stop.set()
        self._watcher.join()
        self._senders.shutdown()
        if any(self.recovered.values()):
            log.warning(f"anchor recoveries (block watcher missed or node lost a transaction): {self.recovered}")
        if self._pending:
            raise RuntimeError(f"{len(self._pending)} anchoring transactions not mined within {self.timeout_s} s")


def make_anchor(cfg: dict):
    return BesuAnchor(cfg) if cfg["ledger"]["backend"] == "besu" else InProcessAnchor(cfg)
