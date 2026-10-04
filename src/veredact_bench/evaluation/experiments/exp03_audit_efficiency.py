"""Exp. 3 — audit efficiency, service side (manuscript Fig. 5).

History: each system redacts the shared trace (untimed, common.build_history). VeRedact-PQ is rebuilt per
records_per_batch value, submitting the trace in authorization batches of exactly that size; baselines have
no batches and run once.
Measured: audit() retrieval_ms (query resolution + evidence generation) and evidence_bytes, per n_Q.
n_Q beyond what a system's history holds is recorded as unreachable (S1: one redaction per block).
"""

from veredact_bench.data.dataset import build_dataset
from veredact_bench.evaluation.common import build_history, capability_fields, open_system
from veredact_bench.methods.registry import system_keys
from veredact_bench.methods.scheme import AuditQuery, NotSupported


def histories(cfg, out, rpb_axis):
    """(key, rpb, scheme, counts) for every system of the experiment; the caller tears the scheme down.
    Opens and closes each method's results folder (out.begin / out.end) around its histories."""
    ds = build_dataset(cfg)
    for key in system_keys(cfg):
        if not out.begin(key):
            continue
        for rpb in rpb_axis if key.startswith("veredact") else [None]:
            s = open_system(cfg, key, ds)
            counts = build_history(s, ds.trace, rpb or 1)  # each Phase 4 batch = rpb requests
            if hasattr(s, "index_records"):
                s.index_records()
            yield key, rpb, s, counts, ds
        out.end()


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
            setup_s=s.setup_s,
            **capability_fields(s),
        )
        if n > have:
            out.row(**base, status=f"unreachable: history holds {have} redactions")
            continue
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
            )
        out.log.info(f"  {key:28s} rpb={rpb} history={counts}")
        s.teardown()
