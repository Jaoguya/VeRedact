"""Exp. 3 — audit efficiency, service side (manuscript Fig. 5).

History: each system redacts the shared trace (untimed, common.build_history). VeRedact-PQ (and the
Per-Record Evidence variant) is rebuilt per records_per_batch value, submitting the trace in authorization
batches of exactly that size; baselines have no batches and run once.
Measured: audit() retrieval_ms (query resolution + evidence generation) and evidence_bytes, per n_Q.
n_Q beyond what a system's history holds is recorded as unreachable (S1: one redaction per block).
"""
from ..dataset import build_dataset
from ..registry import system_keys
from ..scheme import AuditQuery, NotSupported
from .common import build_history, capability_fields, open_system


def histories(cfg, exp, rpb_axis):
    """(key, rpb, scheme, counts) for every system of `exp`; the caller tears the scheme down."""
    ds = build_dataset(cfg)
    for key in system_keys(cfg, exp):
        for rpb in (rpb_axis if key.startswith("veredact") else [None]):
            s = open_system(cfg, key, ds)
            counts = build_history(s, ds.trace, rpb or 1)  # each Phase 4 batch = rpb requests
            if hasattr(s, "index_records"):
                s.index_records()
            yield key, rpb, s, counts, ds


def query_rows(cfg, out, exp, key, rpb, s, counts, ds, n_q_axis, extra=lambda s, n: [dict(query=AuditQuery(n))]):
    out.dataset(ds.dataset_id)
    have = counts["redacted"]
    for n in n_q_axis:
        base = dict(experiment=exp, system=key, records_per_batch=rpb if rpb else "n/a (no batches)", n_Q=n,
                    history_redactions=have, setup_s=s.setup_s, **capability_fields(s))
        if n > have:
            out.row(**base, status=f"unreachable: history holds {have} redactions")
            continue
        for spec in extra(s, n):
            for rep in range(cfg["meta"]["repetitions"]):
                try:
                    res = s.audit(spec["query"])
                except NotSupported as e:
                    out.row(**base, status=f"NotSupported: {e}")
                    return
                yield base, spec, rep, res


def run(cfg, out):
    x = cfg["experiments"]["exp3"]
    for key, rpb, s, counts, ds in histories(cfg, "exp3", x["records_per_batch"]):
        for base, _, rep, res in query_rows(cfg, out, "exp3", key, rpb, s, counts, ds, x["n_Q"]):
            out.row(**base, status="ok", rep=rep, semantics=res.semantics, retrieval_ms=res.retrieval_ms,
                    evidence_bytes=res.evidence_bytes, bytes_per_record=res.evidence_bytes / base["n_Q"])
        print(f"  {key:28s} rpb={rpb} history={counts}", flush=True)
        s.teardown()
