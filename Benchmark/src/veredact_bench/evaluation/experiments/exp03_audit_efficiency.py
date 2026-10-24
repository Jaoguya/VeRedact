"""Exp. 3 — audit and verification efficiency (VeRedact-optimize.tex Fig. 5).

History: every system applies the SAME request list (data/history.py: the shared trace + a seeded top-up of
distinct transactions up to the largest n_Q; untimed, common.build_history). VeRedact-PQ submits it in
authorization batches of records_per_batch; baselines have no batches. A history is saved after it is built and
loaded by later runs (evaluation/history_cache.py, safeguards there); index_records always runs after it.
Measured per n_Q and records per authorization batch (the evidence-sharing axis): response generation
(retrieval_ms), response size (evidence_bytes), auditor-side routine verification (verify_ms, d_Q = 0, a
fresh auditor per query) and the cryptographically verified evidence nodes (VeRedact-PQ systems).
The audit-only variants (shared-evidence, per-record) audit the history VeRedact-PQ built (HISTORY_OF).
When Exp. 4 runs next in the same process, each history is kept and handed to it (SHARED) instead of being
rebuilt: same dataset, records per batch and largest n_Q, so it is the identical history (2026-10-17: at a
10^6 ledger the untimed history build dominates both experiments).
"""

from veredact_bench.data.dataset import build_dataset
from veredact_bench.data.history import history_requests
from veredact_bench.evaluation import history_cache
from veredact_bench.evaluation.common import build_history, capability_fields, open_system
from veredact_bench.methods.registry import system_keys
from veredact_bench.methods.scheme import AuditQuery, NotSupported

# (system, records per batch, history_id) -> (scheme, counts): histories kept for Exp. 4.
# KEEP is set by the runner when exp04_verification_time follows in the same run.
SHARED: dict = {}
KEEP = False
# audit-only variants: same Phases 3-5 as VeRedact-PQ, so they reuse its history (built or loaded once)
HISTORY_OF = {"veredact-shared-evidence": "veredact", "veredact-per-record": "veredact"}


def _history_key(key, rpb, counts) -> tuple:
    return key, rpb, counts["history_id"]


def histories(cfg, out, rpb_axis):
    """(key, rpb, scheme, counts) for every system of the experiment; the caller hands the scheme to done().
    Opens and closes each method's results folder (out.begin / out.end) around its histories."""
    ds = build_dataset(cfg)
    need = max(cfg["experiment"]["n_Q"])
    reqs, hid = history_requests(cfg, ds, need)  # one list for every system (data/history.py)
    for key in system_keys(cfg):
        if not out.begin(key):
            continue
        for rpb in rpb_axis if key.startswith("veredact") else [None]:
            kept = SHARED.pop((key, rpb, hid), None)
            if kept:
                s, counts = kept
                out.log.info(f"  {key:28s} history reused from exp03_audit_efficiency: {counts}")
            else:
                hkey = HISTORY_OF.get(key, key)
                got = history_cache.load(cfg, hkey, rpb, hid, ds, need)
                if got:
                    s, counts = got
                    counts = counts | {"history_source": "cache"}
                else:
                    s = open_system(cfg, hkey, ds)
                    counts = build_history(s, reqs, rpb or 1)  # each Phase 4 batch = rpb requests
                    if counts["redacted"] < need:  # never a silently missing point (author rule 2026-10-05)
                        raise RuntimeError(f"{key}: the history list gave {counts['redacted']} < {need} redactions")
                    counts = counts | {"history_id": hid}
                    history_cache.save(cfg, hkey, rpb, hid, ds, need, s, counts)
                    counts = counts | {"history_source": "built"}
                if hkey != key:
                    s.set_variant(key.partition("-")[2])
                if hasattr(s, "index_records"):  # after every load too: S13 witnesses are re-timed, never saved
                    s.index_records()
            yield key, rpb, s, counts, ds
        out.end()


def done(cfg, key, rpb, s, counts, ds, keep: bool = False) -> None:
    """Tear the scheme down, or keep its history for Exp. 4 (keep=True)."""
    if keep:
        SHARED[_history_key(key, rpb, counts)] = (s, counts)
    else:
        s.teardown()


def release() -> None:
    """Tear down every history Exp. 4 did not take (its method was skipped or already complete)."""
    while SHARED:
        s, _ = SHARED.popitem()[1]
        s.teardown()


def query_rows(cfg, out, key, rpb, s, counts, ds, n_q_axis, extra=lambda s, n: [dict(query=AuditQuery(n))]):
    exp = cfg["experiment"]["id"]
    out.dataset(ds.dataset_id)
    have = counts["redacted"]
    for n in n_q_axis:
        base = dict(
            experiment=exp,
            system=key,
            records_per_batch=rpb if rpb else "n/a (no batches)",
            n_Q=n,
            history_redactions=have,
            history_id=counts["history_id"],
            history_source=counts["history_source"],
            setup_s=s.setup_s,
            **capability_fields(s),
            # S13 only: serial / parallel per-witness time (its witnesses are timed in a process pool)
            **({"witness_calibration": s.witness_calibration} if hasattr(s, "witness_calibration") else {}),
        )
        if n > have:  # the history list reaches max n_Q: a shortfall is a bug, never a missing point
            raise RuntimeError(f"{key}: n_Q={n} but the history holds only {have} redactions")
        k = cfg["experiment"]["samples_per_point"]
        k = cfg["experiment"].get("samples_override", {}).get(key, {}).get(str(n), k)  # S13 at 10^4 (Exp. 3)
        for spec in extra(s, n):
            for sample in range(k):  # queries per point, one run
                try:
                    res = s.audit(spec["query"])
                except NotSupported as e:
                    out.row(**base, status=f"NotSupported: {e}")
                    return
                yield base, spec, sample, res


def run(cfg, out):
    x = cfg["experiment"]
    for key, rpb, s, counts, ds in histories(cfg, out, x["records_per_batch"]):
        for base, _, sample, res in query_rows(cfg, out, key, rpb, s, counts, ds, x["n_Q"]):
            out.row(
                **base,
                status="ok",
                sample=sample,
                semantics=res.semantics,
                retrieval_ms=res.retrieval_ms,
                evidence_bytes=res.evidence_bytes,
                bytes_per_record=res.evidence_bytes / base["n_Q"],
                verify_ms=res.verify_ms,
                all_accepted=int(all(res.accepted.values())),
                **{f"nodes_{k}": v for k, v in res.verified_nodes.items()},
            )
        out.log.info(f"  {key:28s} rpb={rpb} history={counts}")
        done(cfg, key, rpb, s, counts, ds, keep=KEEP)
