"""S99 Li et al. (LETA) — reproduce the paper's evaluation with the construction (FIPS 204 ring, rank from config).

  Table IV : T_a polynomial addition, T_m polynomial multiplication, T_h hash
  Fig. 5   : signature generation (n vehicles sign), aggregate-signature verification, total cost vs vehicles
  Not reproduced: Figs. 6-7 (VPD-Tree tracing in microseconds) — tracing is outside the comparison.
Output: results/reproduction/S99/table4_ops.csv, S99/fig5_cost.csv
Usage:  python scripts/paper_reproduction.py s99_leta [--quick]
"""

import hashlib
import os

import numpy as np

from veredact_bench.methods.baselines.reproduce_common import Csv, cli, median_ms, scheme_config
from veredact_bench.methods.baselines.s99_leta import construction as L
from veredact_bench.methods.baselines.s99_leta.adapter import params
from veredact_bench.utils.config import load


def table4(op_reps):
    out = Csv("S99_table4_ops")
    rng = np.random.default_rng()
    a, b = rng.integers(0, L.Q, L.N), rng.integers(0, L.Q, L.N)
    out.add(
        T_a_ms=median_ms(lambda: (a + b) % L.Q, op_reps),
        T_m_ms=median_ms(lambda: L.intt(L.ntt(a) * L.ntt(b) % L.Q), op_reps),
        T_h_ms=median_ms(lambda: hashlib.sha3_256(os.urandom(64)).digest(), op_reps),
    )
    out.save()


def fig5(S, sweep, reps):
    out = Csv("S99_fig5_cost")
    vs = [L.register(S, b"V%d" % i) for i in range(max(sweep))]
    for n in sweep:
        msgs = [os.urandom(32) for _ in range(n)]
        gen = median_ms(lambda: [L.sign(S, vs[i], msgs[i]) for i in range(n)], reps)
        sigs = [L.sign(S, vs[i], msgs[i]) for i in range(n)]
        leaves = [L.vpd_leaf(vs[i].pseudonym, sigs[i], b"\0" * 32, 1) for i in range(n)]
        members = [(vs[i].pseudonym, 1, sigs[i].mu) for i in range(n)]
        root = L.vpd_root(leaves)
        agg = L.aggregate(S, sigs, members, root, 1)
        args = (agg, members, [s.mu for s in sigs], [v.b for v in vs[:n]], [s.c for s in sigs])
        ver = median_ms(lambda: L.agg_verify(S, *args, now=1, dt=1), reps)
        ok = L.agg_verify(S, *args, now=1, dt=1)
        out.add(vehicles=n, sign_ms=gen, verify_ms=ver, total_ms=gen + ver, aggregate_valid=ok)
    out.save()


if __name__ == "__main__":
    a = cli(__doc__)
    cfg = scheme_config("S99", a.quick)
    S = L.setup(params(load("experiment")))
    print("== S99 Table IV")
    table4(cfg["op_reps"])
    print("== S99 Fig. 5")
    fig5(S, cfg["vehicles_sweep"], cfg["reps"])
