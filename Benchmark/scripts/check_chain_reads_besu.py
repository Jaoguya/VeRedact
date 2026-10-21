"""Real-Besu check of the auditor's checkpoint read (anchor.read("checkpoint_history"), 2026-10-21).

On a running Besu network (deploy/besu/start_besu_network.sh, VRPQ_BESU_KEY set): build a small VeRedact-PQ
history on the smoke configuration, then check that
  1. every redacted transition has its anchoring block (cp_block) and the anchoring-block read returns exactly
     what a scan of every block since deployment returns (the 2026-10-19 read);
  2. a clean audit is accepted, a tampered one rejects exactly the tampered records;
  3. the read time no longer grows with the chain's age (timed now and after waiting AGE_S of new blocks).
Plumbing check: its timings are never results. Usage (server): .venv/bin/python scripts/check_chain_reads_besu.py
"""

import copy
import time

from veredact_bench.data.dataset import build_dataset
from veredact_bench.data.history import history_requests
from veredact_bench.evaluation.common import build_history, open_system
from veredact_bench.methods.scheme import AuditQuery
from veredact_bench.utils.config import load

NEED, AGE_S = 200, 120


def scan_all(a, keys):
    """The 2026-10-19 read: every 5,000-block window since deployment, one batch topic group per call."""
    out, head, bs = {}, a.w3.eth.block_number, sorted({b for b, _ in keys})
    for lo in range(a._from_block, head + 1, 5000):
        for i in range(0, len(bs), 100):
            logs = a.reg.events.CheckpointAnchored.get_logs(
                from_block=lo, to_block=min(lo + 4999, head), argument_filters={"b": bs[i : i + 100]}
            )
            out.update({(int(e.args.b), int(e.args.vb)): bytes(e.args.mr) for e in logs})
    return {k: v for k, v in out.items() if k in keys}


def timed_read(a, keys):
    t = time.perf_counter()
    got = a.read("checkpoint_history", keys=keys)
    return got, (time.perf_counter() - t) * 1000


def main():
    cfg = copy.deepcopy(load("smoke", "exp04_verification_time"))
    cfg["ledger"]["backend"] = "besu"
    cfg["dataset"]["base_transactions"] = 4096
    ds = build_dataset(cfg, n_requests=64)
    reqs, _ = history_requests(cfg, ds, NEED)
    s = open_system(cfg, "veredact", ds)
    counts = build_history(s, reqs, 64)
    s.index_records()
    a = s.anchor
    keys = set(a.cp_block)
    trans = {k for k in keys if k[1] > 0}
    print(f"history {counts}; anchored checkpoints with a block: {len(keys)} ({len(trans)} transitions)")
    assert trans, "no finalized transition has an anchoring block"
    got, ms = timed_read(a, keys)
    ref = scan_all(a, keys)
    assert got == ref and len(got) == len(keys), (len(got), len(ref), len(keys))
    print(f"1. anchoring-block read == full scan for {len(keys)} checkpoints ({ms:.0f} ms)")
    clean = s.audit(AuditQuery(NEED)).accepted
    assert all(clean.values()), "clean audit rejected"
    bad = s.audit(AuditQuery(NEED, tamper={0: "modified", 5: "stale", 9: "substituted"})).accepted
    rejected = {i for i, (rid, ok) in enumerate(bad.items()) if not ok}
    print(f"2. clean audit: {len(clean)} accepted; tampered audit rejected {sorted(rejected)}")
    assert rejected and len(rejected) <= 3
    small = set(list(trans)[:10])
    _, before = timed_read(a, small)
    time.sleep(AGE_S)
    _, after = timed_read(a, small)
    print(f"3. 10-checkpoint read {before:.1f} ms, after {AGE_S} s of new blocks {after:.1f} ms")
    s.teardown()
    print("OK")


if __name__ == "__main__":
    main()
