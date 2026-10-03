"""One seeded corpus + one request trace, shared by every system (docs/experiments.md §1).

Deterministic: the same [meta].seed and [dataset]/[workload] values produce the byte-identical dataset,
whose digest (dataset_id) is written into every result file.
"""
import hashlib
import random

import numpy as np

from veredact_bench.methods.scheme import Dataset, RedactionRequest, Transaction

FAULTS = ("sig", "zk", "policy", "stale", "replay", "absent")


def build_dataset(cfg: dict, n_requests: int | None = None, rate: float | None = None,
                  zipf_s: float | None = None, fault_fraction: float = 0.0, seed_offset: int = 0) -> Dataset:
    d, w = cfg["dataset"], cfg["workload"]
    seed = cfg["meta"]["seed"] + seed_offset
    rng = random.Random(seed)
    nrng = np.random.default_rng(seed)
    txs = []
    for i in range(d["base_transactions"]):
        size = rng.randint(d["payload_min_bytes"], d["payload_max_bytes"])
        txs.append(Transaction(f"TX{i}".encode(), rng.randbytes(size), i % d["requesters"],
                               i % d["policies"], 1_700_000_000 + i))

    # targets: Zipf over transaction batches (s = 0 -> uniform), uniform inside the batch
    N = d["leaves_per_batch"]
    n_batches = (len(txs) + N - 1) // N
    s = w["zipf_s"] if zipf_s is None else zipf_s
    ranks = np.arange(1, n_batches + 1, dtype=float)
    p = ranks ** (-s) if s > 0 else np.ones(n_batches)
    p /= p.sum()
    order = nrng.permutation(n_batches)  # hot batches are not simply the oldest

    n_req = n_requests or w["total_requests"]
    rate = rate or 1.0
    t, trace = 0.0, []
    for seq in range(n_req):
        t += nrng.exponential(1.0 / rate)
        b = order[nrng.choice(n_batches, p=p)]
        idx = min(b * N + int(nrng.integers(N)), len(txs) - 1)
        fault = rng.choice(FAULTS) if rng.random() < fault_fraction else ""
        trace.append(RedactionRequest(seq, rng.randrange(d["requesters"]), txs[idx].tid,
                                      rng.randbytes(rng.randint(d["payload_min_bytes"], d["payload_max_bytes"])),
                                      t, fault))
    h = hashlib.sha3_256()
    h.update(repr((seed, d, w, n_req, rate, s, fault_fraction)).encode())
    for tx in txs[:: max(1, len(txs) // 1024)]:
        h.update(tx.tid + tx.payload[:32])
    return Dataset(seed, txs, d["requesters"], d["policies"], trace, h.hexdigest()[:16])
