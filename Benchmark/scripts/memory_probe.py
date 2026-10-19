"""Memory probe for the 10^6-ledger / n_Q = 10^5 run (2026-10-19): real data structures, no measurements.

Per scheme (one process each, so peak memory is per scheme): dataset, history list, setup, then a history of
H1 and H2 redactions (real redactions, in-process ledger), and a save of the state with history_cache's pickler.
Memory per redaction = (RSS at H2 - RSS at H1) / (H2 - H1); 10^5 is extrapolated linearly (state grows with
records). Prints one JSON line per scheme. Usage: .venv/bin/python scripts/memory_probe.py [H1 H2]"""

import copy
import json
import multiprocessing as mp
import os
import resource
import sys
import time

H1, H2 = (int(sys.argv[1]), int(sys.argv[2])) if len(sys.argv) > 2 else (1000, 10000)
TARGET = 100_000


def rss_gb() -> float:
    return int(open("/proc/self/statm").read().split()[1]) * os.sysconf("SC_PAGE_SIZE") / 2**30


def peak_gb() -> float:
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 2**20


def probe(key: str, q) -> None:
    from veredact_bench.data.dataset import build_dataset
    from veredact_bench.data.history import history_requests
    from veredact_bench.evaluation import history_cache
    from veredact_bench.evaluation.common import build_history, open_system
    from veredact_bench.utils.config import load

    out, t0 = {"scheme": key}, time.time()
    cfg = copy.deepcopy(load("experiment", "exp03_audit_efficiency"))
    cfg["ledger"]["backend"] = "in_process"  # same scheme state; Besu holds the chain in its own processes
    ds = build_dataset(cfg)
    out["dataset_gb"] = round(rss_gb(), 2)
    reqs, _ = history_requests(cfg, ds, TARGET)
    out["history_list_gb"] = round(rss_gb() - out["dataset_gb"], 2)
    base = rss_gb()
    s = open_system(cfg, key, ds)
    out["setup_gb"] = round(rss_gb() - base, 2)
    rpb = cfg["veredact"]["reference_batch"] if key == "veredact" else 1
    marks = {}
    done = 0
    for h in (H1, H2):
        c = build_history(s, reqs[done:h], rpb)
        done = h
        marks[h] = (rss_gb(), len(getattr(s, "redacted", [])) or c["redacted"])
    per = (marks[H2][0] - marks[H1][0]) / (H2 - H1)
    out["mb_per_redaction"] = round(per * 1024, 4)
    out["at_H2_gb"] = round(marks[H2][0], 2)
    out["history_1e5_gb"] = round(per * TARGET, 2)
    before = peak_gb()
    path = f"/tmp/memprobe_{key}.pkl"
    s_anchor = s.anchor
    with open(path, "wb") as f:
        history_cache._Pickler(f, protocol=5).dump((s, {"redacted": H2}))
    out["save_file_gb_at_H2"] = round(os.path.getsize(path) / 2**30, 3)
    out["save_file_gb_1e5_est"] = round(os.path.getsize(path) / 2**30 * TARGET / H2, 2)
    out["save_extra_peak_gb_at_H2"] = round(max(0.0, peak_gb() - before), 2)
    os.remove(path)
    s_anchor.close()
    out["peak_gb"] = round(peak_gb(), 2)
    out["minutes"] = round((time.time() - t0) / 60, 1)
    q.put(out)


if __name__ == "__main__":
    os.environ.setdefault("VRPQ_SIG_BACKEND", "oqs")
    q = mp.get_context("spawn").Queue()
    ps = [mp.get_context("spawn").Process(target=probe, args=(k, q)) for k in ("veredact", "S1", "S13")]
    for p in ps:
        p.start()
    for _ in ps:
        print(json.dumps(q.get()), flush=True)
    for p in ps:
        p.join()
