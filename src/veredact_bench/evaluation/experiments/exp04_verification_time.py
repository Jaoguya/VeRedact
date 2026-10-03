"""Exp. 4 — verification time, auditor side (manuscript Fig. 6), with fault injection.

History as in Exp. 3 (VeRedact-PQ submitted in batches of veredact.reference_batch). Per n_Q, level and
injected fraction f: a seeded f * n_Q of the returned records are tampered (modified content,
substituted evidence, stale version — cycled), the auditor verifies, and every record's decision is
written. f = 0 (no injection) is always run: it is the clean verification time.
Levels: VeRedact-PQ distinguishes normal/deep; a baseline whose audit has one level runs it for both and
the row says so (level_supported = 0). S13 decides for the whole query (one bad record rejects all):
that shows up here as false rejections, which is the protocol's real behaviour.
"""

import random

from veredact_bench.evaluation.experiments.exp03_audit_efficiency import histories, query_rows
from veredact_bench.methods.scheme import AuditQuery

KINDS = ("modified", "substituted", "stale")
# Fig. 6(b): response signature + query binding, RAI multiproof, committee approvals, attestations,
# state-transition and PQCH checks, PQZK (VeRedact-PQ reports these; baselines leave them empty)
BREAKDOWN = ("response_ms", "rai_mp_ms", "committee_ms", "attest_ms", "state_ms", "zk_ms")


def run(cfg, out):
    x = cfg["experiment"]
    for key, rpb, s, counts, ds in histories(cfg, out, [cfg["veredact"]["reference_batch"]]):

        def specs(s, n):
            for level in x["levels"]:
                for f in [0.0, *x["inject_fractions"]]:
                    rng = random.Random(cfg["meta"]["seed"] + n)
                    idx = rng.sample(range(n), round(f * n))
                    tamper = {i: KINDS[j % len(KINDS)] for j, i in enumerate(sorted(idx))}
                    yield dict(query=AuditQuery(n, deep=level == "deep", tamper=tamper), level=level, f=f)

        for base, spec, sample, res in query_rows(cfg, out, key, rpb, s, counts, ds, x["n_Q"], specs):
            t = spec["query"].tamper
            acc = res.accepted
            out.row(
                **base,
                status="ok",
                sample=sample,
                level=spec["level"],
                level_supported=int(key.startswith("veredact")),
                inject_fraction=spec["f"],
                injected=len(t),
                verify_ms=res.verify_ms,
                retrieval_ms=res.retrieval_ms,
                detected=sum(1 for i in t if not acc.get(i, False)),
                false_rejections=sum(1 for i, ok in acc.items() if not ok and i not in t),
                semantics=res.semantics,
                **{f"verify_{k}": res.breakdown.get(k, "") for k in BREAKDOWN},
            )
        out.log.info(f"  {key:28s} history={counts}")
        s.teardown()
