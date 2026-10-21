"""The redaction-history request list of Exp. 3/4, one list for every scheme (author decision 2026-10-19).

The history is the shared request trace followed by a seeded top-up of requests to DISTINCT transactions not
targeted before, until the list targets `need` (= the largest n_Q) distinct transactions plus a small margin.
Every scheme applies the same list in the same order, so S1 (one redaction per block, one transaction per
block) and the schemes that also accept a second redaction of a transaction redact the same records; S1 only
rejects the trace's repeated targets.

Deterministic: the same dataset and `need` give the byte-identical list, whose digest is `history_id`
(written into every Exp. 3/4 row and checked by the history cache and the coverage check).
"""

import hashlib
import random

from veredact_bench.methods.scheme import RedactionRequest

VERSION = 1  # bump when the generator changes: every saved history built from an older list is refused
MARGIN = 0.005  # extra distinct targets, so a scheme that rejects a handful of requests still reaches `need`


def history_requests(cfg: dict, ds, need: int) -> tuple[list, str]:
    d = cfg["dataset"]
    reqs = list(ds.trace)
    targeted = {r.tid for r in reqs}
    want = int(need * (1 + MARGIN)) + 1
    if want > len(ds.transactions):
        raise ValueError(f"history needs {want} distinct transactions, the ledger holds {len(ds.transactions)}")
    rng = random.Random(cfg["meta"]["seed"] + 7919)
    free = [tx for tx in ds.transactions if tx.tid not in targeted]
    rng.shuffle(free)
    seq = max((r.seq for r in reqs), default=-1) + 1
    for tx in free[: max(0, want - len(targeted))]:
        payload = rng.randbytes(rng.randint(d["payload_min_bytes"], d["payload_max_bytes"]))
        reqs.append(RedactionRequest(seq, rng.randrange(ds.requesters), tx.tid, payload, 0.0))
        seq += 1
    h = hashlib.sha3_256(repr((VERSION, ds.dataset_id, need, len(reqs))).encode())
    for r in reqs:
        h.update(r.tid + r.new_payload[:32] + r.requester.to_bytes(4, "big") + r.fault.encode())
    return reqs, h.hexdigest()[:16]
