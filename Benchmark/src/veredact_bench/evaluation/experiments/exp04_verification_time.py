"""Exp. 4 — selective verification and evidence integrity, auditor side (VeRedact-optimize.tex Fig. 6).

History as in Exp. 3 (VeRedact-PQ submitted in authorization batches of veredact.reference_batch); when Exp. 3
ran just before in the same process, its histories are reused (exp03_audit_efficiency.SHARED).
Two sweeps per n_Q, each query verified by a fresh auditor (empty verified-context store):
  escalation  the fraction d_Q / n_Q of returned requests escalated to independent PQZK verification
              (experiment.deep_fractions); routine verification is d_Q = 0. Baselines define no escalation and
              run only d_Q = 0 (escalation_supported = 0).
  integrity   at d_Q = 0, a seeded fraction f of the returned records is tampered with ONE fault class at a time
              (modified evidence, substituted evidence, stale evidence); every record's decision is written, so
              the invalid-record rejection rate and the valid-record acceptance rate follow per class. S13 decides
              for the whole query (one bad record rejects all): false rejections there are its real behaviour.
"""

import random

from veredact_bench.evaluation.experiments.exp03_audit_efficiency import histories, query_rows, release
from veredact_bench.methods.scheme import AuditQuery

KINDS = ("modified", "substituted", "stale")
# verification-time breakdown (manuscript Fig. 6(b)): RAI and response authentication, request attestations,
# committee approvals, transition/PQCH, finalized checkpoints, PQZK (VeRedact-PQ; baselines leave them empty)
BREAKDOWN = ("response_ms", "rai_mp_ms", "attest_ms", "committee_ms", "state_ms", "cp_ms", "zk_ms")


def run(cfg, out):
    try:
        _run(cfg, out)
    finally:
        release()  # histories kept by Exp. 3 for a method this run did not take


def _run(cfg, out):
    x = cfg["experiment"]
    for key, rpb, s, counts, ds in histories(cfg, out, [cfg["veredact"]["reference_batch"]]):
        escalates = key.startswith("veredact")

        def specs(s, n, escalates=escalates):
            for d in x["deep_fractions"] if escalates else [0.0]:
                yield dict(query=AuditQuery(n, deep_fraction=d, reuse_response=True), d=d, kind="", f=0.0)
            for kind in KINDS:
                for f in x["inject_fractions"]:
                    rng = random.Random(cfg["meta"]["seed"] + n)
                    idx = rng.sample(range(n), round(f * n))
                    # reuse_response: Exp. 4 times the auditor; a scheme whose response generation is slow (S13:
                    # one accumulator witness per record) builds it once and is verified samples_per_point times
                    q = AuditQuery(n, tamper={i: kind for i in idx}, reuse_response=True)
                    yield dict(query=q, d=0.0, kind=kind, f=f)

        for base, spec, sample, res in query_rows(cfg, out, key, rpb, s, counts, ds, x["n_Q"], specs):
            t = spec["query"].tamper
            acc = res.accepted
            out.row(
                **base,
                status="ok",
                sample=sample,
                escalation_supported=int(escalates),
                deep_fraction=spec["d"],
                fault_kind=spec["kind"] or "none",
                inject_fraction=spec["f"],
                injected=len(t),
                verify_ms=res.verify_ms,
                retrieval_ms=res.retrieval_ms,
                detected=sum(1 for i in t if not acc.get(i, False)),
                false_rejections=sum(1 for i, ok in acc.items() if not ok and i not in t),
                semantics=res.semantics,
                **{f"verify_{k}": res.breakdown.get(k, "") for k in BREAKDOWN},
                **{f"nodes_{k}": v for k, v in res.verified_nodes.items()},
            )
        out.log.info(f"  {key:28s} history={counts}")
        s.teardown()
