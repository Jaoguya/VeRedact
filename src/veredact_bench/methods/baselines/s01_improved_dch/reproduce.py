"""S1 [1] Li et al. — reproduce the paper's evaluation with the original construction.

  Table II : per-participant execution time of KeyGen / Hash / Verify / Collision, DCH vs Improved DCH (t = 5)
  Fig. 2   : KeyGen and Collision time vs number of participants t
  Sec. IV  : the attack — a forged Jia-DCH redaction verifies; the same trick fails on Improved DCH
Output: results/S1_table2_times.csv, results/S1_fig2_scaling.csv, results/S1_attack.csv
Usage:  python scripts/paper_reproduction.py s01_improved_dch [--quick]
"""

from veredact_bench.methods.baselines.reproduce_common import Csv, cli, median_ms, scheme_config
from veredact_bench.methods.baselines.s01_improved_dch.construction import (
    SIZES,
    ImprovedDCH,
    JiaDCH,
    dkg,
    forge_jia,
    try_forge_improved,
)


def table2(cfg, reps):
    out = Csv("S1_table2_times")
    t = cfg["t_default"]
    key = dkg(t)
    ids = list(key.shares)
    jia, imp = JiaDCH(key), ImprovedDCH(key)
    m, m2 = b"block-header-original", b"block-header-redacted"
    jh = jia.hash(m)
    ih = imp.hash(m)
    jr2 = jia.collision(m, jh.r, m2, ids)
    ops = {
        "DCH [Jia]": {
            "KeyGen": lambda: dkg(t),
            "Hash": lambda: jia.hash(m),
            "Verify": lambda: jia.verify(m, jh.r, m2, jr2),
            "Collision": lambda: jia.collision(m, jh.r, m2, ids),
        },
        "Improved DCH": {
            "KeyGen": lambda: dkg(t),
            "Hash": lambda: imp.hash(m),
            "Verify": lambda: imp.verify(m, ih.r, ih.h),
            "Collision": lambda: imp.collision(m, m2, ih.r, ih.h, ids),
        },
    }
    for scheme, fns in ops.items():
        for alg, fn in fns.items():
            n = cfg["keygen_reps"] if alg == "KeyGen" else reps
            ms = median_ms(fn, n)
            per_party = ms / t if alg in ("KeyGen", "Collision") else ms  # paper reports one participant
            out.add(scheme=scheme, algorithm=alg, t=t, ms_per_participant=per_party, reps=n)
        out.add(scheme=scheme, algorithm="|r| bytes", t=t, ms_per_participant=float(SIZES[scheme]["r_bytes"]), reps=0)
    out.save()


def fig2(cfg, reps):
    out = Csv("S1_fig2_scaling")
    ts = cfg["t_sweep"]
    m, m2 = b"m", b"m'"
    for t in ts:
        key = dkg(t)
        ids = list(key.shares)
        jia, imp = JiaDCH(key), ImprovedDCH(key)
        jh, ih = jia.hash(m), imp.hash(m)
        kg = median_ms(lambda: dkg(t), cfg["keygen_reps"]) / t
        out.add(
            t=t,
            scheme="DCH [Jia]",
            keygen_ms=kg,
            collision_ms=median_ms(lambda: jia.collision(m, jh.r, m2, ids), reps) / t,
        )
        out.add(
            t=t,
            scheme="Improved DCH",
            keygen_ms=kg,
            collision_ms=median_ms(lambda: imp.collision(m, m2, ih.r, ih.h, ids), reps) / t,
        )
    out.save()


def attack():
    out = Csv("S1_attack")
    key = dkg(5)
    ids = list(key.shares)
    jia = JiaDCH(key)
    m, m1, m_evil = b"header0", b"header-honest-redaction", b"header-malicious-redaction"
    h = jia.hash(m)
    r1 = jia.collision(m, h.r, m1, ids)  # honest threshold redaction (published on-chain)
    r_evil = forge_jia(jia, m, h.r, m1, r1, m_evil)  # single malicious node, no trapdoor shares
    out.add(
        scheme="DCH [Jia]",
        honest_redaction_valid=jia.verify(m, h.r, m1, r1),
        forged_redaction_valid=jia.verify(m, h.r, m_evil, r_evil),
    )
    imp = ImprovedDCH(key)
    ih = imp.hash(m)
    ir1 = imp.collision(m, m1, ih.r, ih.h, ids)
    out.add(
        scheme="Improved DCH",
        honest_redaction_valid=imp.verify(m1, ir1, ih.h),
        forged_redaction_valid=try_forge_improved(imp, m, ih.r, m1, ir1, ih.h, m_evil),
    )
    out.save()


if __name__ == "__main__":
    a = cli(__doc__)
    cfg = scheme_config("S1", a.quick)
    reps = cfg["reps"]
    print("== S1 Table II")
    table2(cfg, reps)
    print("== S1 Fig. 2")
    fig2(cfg, reps)
    print("== S1 attack (Sec. IV)")
    attack()
