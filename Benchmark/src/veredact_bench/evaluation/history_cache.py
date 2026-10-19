"""Saved redaction histories of Exp. 3/4 (author decision 2026-10-19): built once, loaded by later runs.

A history is untimed setup (common.build_history over data/history.py's request list), so reusing it changes no
reported number. Layout: <output.dir>/_histories/<history_id>/<method>-rpb<r>/{state.pkl, oplog.pkl, meta.json}.

  state.pkl  the scheme after its history, pickled with live handles replaced by tokens (_Pickler): the anchor,
             Futures, locks and modules are recreated; the STARK registry is rebuilt from its seed (root checked);
             BLS12-381 points and secp256k1 keys travel as bytes
  oplog.pkl  every anchoring operation the scheme submitted, in order: loading replays it into a FRESH
             deployment, so the chain holds exactly what the auditor reads (anchor.read) — no Besu snapshot
  meta.json  what the history was built from

Safeguards (a mismatch rebuilds, it never reuses):
  - history_id (dataset_id + request list), dataset_id, the configuration that shapes the state (dataset,
    security, veredact, baselines.<method>, ledger backend, seed) and a digest of the code that builds it
    (methods/, data/, evaluation/anchor.py, evaluation/common.py, this file, contracts/);
  - after loading: redactions >= the largest n_Q, the STARK registry root equals the saved one.
Witness-style audit preparation (index_records: S13 witnesses, S1 membership proofs, VeRedact-PQ RAI) is NOT
saved: it runs, and is timed where it is timed, after every load. VRPQ_HISTORY_CACHE=0 disables the cache.
"""

import hashlib
import json
import os
import pickle
import threading
import time
import types
from concurrent.futures import Future
from dataclasses import asdict

from veredact_bench.evaluation import anchor as anchor_mod
from veredact_bench.utils.config import REPO_ROOT
from veredact_bench.utils.log import get_logger

SRC = REPO_ROOT / "src" / "veredact_bench"
CODE = [
    SRC / "methods",
    SRC / "data",
    SRC / "evaluation" / "anchor.py",
    SRC / "evaluation" / "common.py",
    SRC / "evaluation" / "history_cache.py",
    REPO_ROOT / "contracts",
]
_LOCKS = (type(threading.Lock()), type(threading.RLock()))
REPLAY_WINDOW = 2000  # anchoring transactions in flight while a saved history is replayed (~15 s of blocks)


def enabled() -> bool:
    return os.environ.get("VRPQ_HISTORY_CACHE", "1") != "0"


def code_digest() -> str:
    h = hashlib.sha3_256()
    for root in CODE:
        files = sorted(root.rglob("*")) if root.is_dir() else [root]
        for f in files:
            if f.is_file() and f.suffix in (".py", ".sol"):
                h.update(str(f.relative_to(REPO_ROOT)).encode() + f.read_bytes())
    return h.hexdigest()[:16]


def config_digest(cfg: dict, key: str) -> str:
    base = key.split("-")[0]
    part = {
        "dataset": cfg["dataset"],
        "security": cfg["security"],
        "veredact": cfg["veredact"] if base == "veredact" else None,
        "baseline": cfg["baselines"].get(base),
        "ledger": cfg["ledger"]["backend"],
        "seed": cfg["meta"]["seed"],
    }
    return hashlib.sha3_256(json.dumps(part, sort_keys=True, default=str).encode()).hexdigest()[:16]


def _dir(cfg: dict, history_id: str, key: str, rpb):
    return REPO_ROOT / cfg["output"]["dir"] / "_histories" / history_id / f"{key}-rpb{rpb}"


def _show(d) -> str:
    return str(d.relative_to(REPO_ROOT)) if d.is_relative_to(REPO_ROOT) else str(d)


def _meta(cfg, key, rpb, history_id, ds, need) -> dict:
    return {
        "history_id": history_id,
        "dataset_id": ds.dataset_id,
        "method": key,
        "rpb": rpb,
        "need": need,
        "config_digest": config_digest(cfg, key),
        "code_digest": code_digest(),
    }


class _Pickler(pickle.Pickler):
    def persistent_id(self, o):
        if isinstance(o, (anchor_mod.BesuAnchor, anchor_mod.InProcessAnchor)):
            return ("ANCHOR",)
        if isinstance(o, Future):
            return ("FUTURE",)
        if isinstance(o, types.ModuleType):
            return ("MODULE", o.__name__)
        if isinstance(o, _LOCKS):
            return ("LOCK", isinstance(o, _LOCKS[1]))
        name = type(o).__name__
        if name == "PolicySTARK":
            if o.seed is None:
                raise pickle.PicklingError("unseeded STARK registry cannot be rebuilt: refusing to save the history")
            return ("STARK", asdict(o.p), o.requesters, o.seed, o.now_s, o.root)
        if name in ("G1Point", "G2Point"):
            return (name, bytes(o.to_compressed_bytes()))
        if type(o).__module__.startswith("coincurve"):
            if name == "PrivateKey":
                return ("CC_SK", o.secret)
            if name == "PublicKey":
                return ("CC_PK", o.format())
        return None


class _Unpickler(pickle.Unpickler):
    def __init__(self, f, anchor):
        super().__init__(f)
        self.anchor = anchor

    def persistent_load(self, pid):
        kind = pid[0]
        if kind == "ANCHOR":
            return self.anchor
        if kind == "FUTURE":
            f = Future()
            f.set_result((0.0, 0))  # every saved Future was resolved before saving (finality awaited)
            return f
        if kind == "MODULE":
            return __import__(pid[1], fromlist=["_"])
        if kind == "LOCK":
            return threading.RLock() if pid[1] else threading.Lock()
        if kind == "STARK":
            from veredact_bench.methods.veredact.crypto.pqzk_stark import PolicySTARK, ZKParams

            zk = PolicySTARK(ZKParams(**pid[1]), pid[2], pid[3], pid[4])
            if zk.root != pid[5]:
                raise pickle.UnpicklingError("rebuilt STARK registry root differs from the saved one")
            return zk
        if kind in ("G1Point", "G2Point"):
            import py_arkworks_bls12381 as ark

            return getattr(ark, kind).from_compressed_bytes(pid[1])
        if kind == "CC_SK":
            from coincurve import PrivateKey

            return PrivateKey(pid[1])
        if kind == "CC_PK":
            from coincurve import PublicKey

            return PublicKey(pid[1])
        raise pickle.UnpicklingError(f"unknown token {kind}")


def save(cfg, key, rpb, history_id, ds, need, s, counts) -> None:
    """After the history is final (every anchoring Future resolved), before index_records."""
    if not enabled():
        return
    d = _dir(cfg, history_id, key, rpb)
    d.mkdir(parents=True, exist_ok=True)
    t = time.time()
    with open(d / "state.pkl.tmp", "wb") as f:
        _Pickler(f, protocol=5).dump((s, counts))
    with open(d / "oplog.pkl.tmp", "wb") as f:
        pickle.dump(s.anchor.oplog, f, protocol=5)
    os.replace(d / "state.pkl.tmp", d / "state.pkl")
    os.replace(d / "oplog.pkl.tmp", d / "oplog.pkl")
    meta = _meta(cfg, key, rpb, history_id, ds, need) | {"counts": counts, "saved_utc": time.time()}
    (d / "meta.json").write_text(json.dumps(meta, indent=1))  # written last: a partial save has no meta
    get_logger().info(f"  {key:28s} history saved -> {_show(d)} ({time.time() - t:.0f} s)")


def load(cfg, key, rpb, history_id, ds, need):
    """(scheme, counts) restored onto a fresh anchor with the history's transactions replayed, or None."""
    if not enabled():
        return None
    log = get_logger()
    d = _dir(cfg, history_id, key, rpb)
    if not (d / "meta.json").exists():
        return None
    meta = json.loads((d / "meta.json").read_text())
    want = _meta(cfg, key, rpb, history_id, ds, need)
    diff = [k for k in want if meta.get(k) != want[k]]
    if diff:
        log.warning(f"  {key:28s} saved history refused (differs in {diff}): rebuilding")
        return None
    t = time.time()
    anchor = anchor_mod.make_anchor(cfg)
    with open(d / "oplog.pkl", "rb") as f:
        oplog = pickle.load(f)
    # same chain state; at most REPLAY_WINDOW in flight: 10^5 submitted at once would wait ~11 min in the pool at
    # ~150 tx/s, past ledger.receipt_timeout_s (600 s), and fail
    window = []
    for op, fields in oplog:
        window.append(anchor.submit(op, **fields))
        if len(window) >= REPLAY_WINDOW:
            anchor_mod.gather(window).result()
            window = []
    anchor_mod.gather(window).result()
    with open(d / "state.pkl", "rb") as f:
        s, counts = _Unpickler(f, anchor).load()
    if counts["redacted"] < need:
        raise RuntimeError(f"{key}: saved history holds {counts['redacted']} < {need} redactions")
    log.info(
        f"  {key:28s} history loaded from {_show(d)}: {len(oplog)} transactions replayed ({time.time() - t:.0f} s)"
    )
    return s, counts
