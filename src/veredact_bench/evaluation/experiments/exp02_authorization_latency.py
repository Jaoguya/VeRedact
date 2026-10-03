"""Exp. 2 — transaction authorization latency (manuscript Fig. 4).

Boundary: admission -> authorization decision. Requester-side preparation is outside the timer.
  VeRedact-PQ   per request: Phase 3 (authorize); per batch of b: Phase 4 (authorize_batch: attestation +
                C_VR reconstruction + freshness + R_e^VR + t committee ML-DSA signatures). Reported
                separately, as phase3 + phase4/b per request, and Phase 4 split into its four steps.
  baselines     their own per-request authorization; they have no batch axis, so they run at b = 1 only.
committee_n sweeps each system's own distribution parameter (registry.make, t = floor(2n/3)+1).
Valid requests only (fault_fraction = 0): Exp. 2 measures the cost of saying yes.
"""
from veredact_bench.data.dataset import build_dataset
from veredact_bench.methods.registry import distribution_param, system_keys
from veredact_bench.evaluation.common import auth_cost_fields, authorize, capability_fields, is_veredact, open_system, prepare

# Phase 4 per batch, split as in the manuscript: attestation verification, state-freshness checking,
# batch-commitment construction, committee signing and verification
BREAKDOWN = ("attest_ms", "fresh_ms", "commit_ms", "committee_ms")


def run(cfg, out):
    x = cfg["experiment"]
    reps = x["samples_per_point"]  # authorization batches per point, inside the one run
    for key in system_keys(cfg):
        if not out.begin(key):
            continue
        batch_axis = x["batch_sizes"] if key.startswith("veredact") else [1]
        ds = build_dataset(cfg, n_requests=reps * max(batch_axis))
        out.dataset(ds.dataset_id)
        for n in x["committee_sizes"]:
            s = open_system(cfg, key, ds, committee_n=n)
            common = dict(experiment=x["id"], system=key, committee_n=n, distribution_param=distribution_param(key),
                          setup_s=s.setup_s, **auth_cost_fields(s), **capability_fields(s))
            nxt = 0
            for b in batch_axis:
                for sample in range(reps):
                    reqs = ds.trace[nxt:nxt + b]
                    nxt = (nxt + b) % max(1, len(ds.trace) - b)
                    auths = []
                    for r in reqs:
                        a = authorize(s, r, prepare(s, r))
                        auths.append(a)
                    ph4, bd = "", dict.fromkeys(BREAKDOWN, "")
                    if is_veredact(s):
                        _, ph4 = s.authorize_batch(auths)
                        bd = {k: s.p.last_breakdown[k] for k in BREAKDOWN}
                    for a in auths:
                        out.row(**common, batch_size=b, sample=sample, seq=a.request.seq, auth_ok=int(a.ok), reason=a.reason,
                                phase3_ms=a.crypto_ms, phase4_batch_ms=ph4,
                                **{f"phase4_{k}": v for k, v in bd.items()},
                                auth_per_request_ms=a.crypto_ms + (ph4 / b if ph4 != "" else 0.0))
            out.log.info(f"  {key:28s} n={n:<3} batch axis {batch_axis} x {reps} samples")
            s.teardown()
        out.end()
