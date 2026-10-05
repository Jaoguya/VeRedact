"""metrics.json: per-point summary of one (experiment, method) run, computed from its rows with metrics.py.

The rows stay the source of truth (tables and figures read them); metrics.json is the readable
summary a reviewer opens first. Keys are "<axis>=<value>|..." strings so the file stays flat JSON.
"""

from collections import defaultdict

from veredact_bench import metrics as M


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _stats(values) -> dict:
    xs = [x for x in (_num(v) for v in values) if x is not None]
    if not xs:
        return {"n": 0}
    return {
        "n": len(xs),
        "median": M.median(xs),
        "mean": M.mean(xs),
        "p95": M.percentile(xs, 95),
        "ci95_halfwidth": M.ci95_halfwidth(xs),
    }


def _group(rows, *axes, where=lambda r: True):
    g = defaultdict(list)
    for r in rows:
        if where(r):
            g["|".join(f"{a}={r.get(a, '')}" for a in axes)].append(r)
    return g


def _primitives(rows, cfg):
    return {
        k: _stats(r["ms"] for r in rs) | {"instantiation": rs[0]["instantiation"]}
        for k, rs in _group(rows, "symbol", "instantiation").items()
    }


def _exp01(rows, cfg):
    dur = cfg["experiment"]["duration_s"]
    start = cfg["experiment"]["warmup_s"]
    end = start + dur  # the measurement window [start, end) on the run's clock
    out = {}
    for k, rs in _group(rows, "sweep", "rate_rps", "zipf_s").items():
        win = [r for r in rs if str(r["in_window"]) == "1" and not r.get("fault")]
        fin = [r for r in win if r["status"] == "finalized"]
        # Fig. 3(c) counts PQCH adaptations over EVERY finalized redaction of the point (warm-up included): the
        # count does not depend on arrival time, and a scheme saturated at zipf_rate (S13, S34 at the
        # manuscript's lowest rate) finalizes few requests inside the window but still has a value
        done = [r for r in rs if r["status"] == "finalized" and not r.get("fault")]
        # throughput = redactions FINALIZED DURING the window (steady state, any arrival time) / its length. Counting
        # requests that ARRIVED in the window instead credits the drain after it (S27 at 500 req/s: 456/s vs 152/s
        # actually completed) and shows 0 for a saturated scheme that keeps finalizing (S13: 5.3/s) — 2026-10-05.
        fin_t = lambda r: _num(r["submit_s"]) + _num(r["latency_ms"]) / 1000
        completed = [r for r in done if _num(r.get("latency_ms")) is not None and start <= fin_t(r) < end]
        adapt = {r["batch_id"]: _num(r["batch_adaptations"]) for r in done if r.get("batch_id") not in ("", None)}
        out[k] = {
            "offered": len(win),
            "decided": sum(r["status"] in ("finalized", "rejected", "failed") for r in win),
            "revalidations": sum(int(_num(r.get("revalidations")) or 0) for r in win),  # stale -> re-prove
            "submitted_on_time": M.rate(
                sum(_num(r.get("submit_s")) is not None and _num(r["submit_s"]) < end for r in win), len(win)
            ),
            "finalized": len(fin),  # arrived in the window and finalized (any time): kept for traceability
            "completed_in_window": len(completed),
            "throughput_per_s": M.throughput(len(completed), dur),
            "latency_ms": _stats(r["latency_ms"] for r in completed),
            "pqch_adaptations_per_1000": M.per_thousand(sum(adapt.values()), len(done)) if done else None,
        }
    return out


def _exp02(rows, cfg):
    return {
        k: {
            "auth_per_request_ms": _stats(r["auth_per_request_ms"] for r in rs),
            "phase4_batch_ms": _stats(r["phase4_batch_ms"] for r in rs),
            "accepted": sum(int(r["auth_ok"]) for r in rs),
            "requests": len(rs),
        }
        for k, rs in _group(rows, "committee_n", "batch_size").items()
    }


def _exp03(rows, cfg):
    out = {}
    for k, rs in _group(rows, "records_per_batch", "n_Q").items():
        ok = [r for r in rs if r.get("status") == "ok"]
        out[k] = {
            "status": "ok" if ok else rs[0].get("status"),
            "retrieval_ms": _stats(r["retrieval_ms"] for r in ok),
            "evidence_bytes": _stats(r["evidence_bytes"] for r in ok),
        }
    return out


def _exp04(rows, cfg):
    out = {}
    for k, rs in _group(rows, "n_Q", "level", "inject_fraction").items():
        ok = [r for r in rs if r.get("status") == "ok"]
        if not ok:
            out[k] = {"status": rs[0].get("status")}
            continue
        injected = sum(int(r["injected"]) for r in ok)
        valid = sum(int(r["n_Q"]) - int(r["injected"]) for r in ok)
        out[k] = {
            "status": "ok",
            "verify_ms": _stats(r["verify_ms"] for r in ok),
            "detection_rate": M.rate(sum(int(r["detected"]) for r in ok), injected),
            "false_rejection_rate": M.rate(sum(int(r["false_rejections"]) for r in ok), valid),
        }
    return out


def _exp05(rows, cfg):
    out = {}
    for k, rs in _group(rows, "zipf_s", "batch_size").items():
        gas = [_num(r["gas_used"]) for r in rs if _num(r["gas_used"]) is not None]
        red = _num(rs[0]["redactions"]) or 0
        out[k] = {
            "transactions": len(rs),
            "redactions": red,
            "total_gas": sum(gas) if gas else None,
            "gas_per_redaction": sum(gas) / red if gas and red else None,
            "by_operation": {op: _stats(r["gas_used"] for r in g) for op, g in _group(rs, "op").items()},
        }
    return out


SUMMARIES = {
    "exp00_primitives": _primitives,
    "exp01_redaction_throughput": _exp01,
    "exp02_authorization_latency": _exp02,
    "exp03_audit_efficiency": _exp03,
    "exp04_verification_time": _exp04,
    "exp05_gas_consumption": _exp05,
}


def summarize(experiment: str, rows: list[dict], cfg: dict) -> dict:
    return {"experiment": experiment, "rows": len(rows), "points": SUMMARIES[experiment](rows, cfg)}
