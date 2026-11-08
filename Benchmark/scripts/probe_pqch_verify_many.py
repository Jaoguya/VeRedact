"""PROBE, never a result (#13, Other/docs/implementation-plan.md section 6): does the auditor's batched PQCH check
(`verify_many`, one matrix product) beat a loop of `verify` over the same columns, and by how much?

The answer decides whether Exp. 3's headline is ~2 s or ~5 s at n_Q = 10^4 (S4's batching factor), before any AWS
budget is spent on the full run. The PQCH parameters are the experiment tier's (configs/base.yaml security.pqch);
the column count is Exp. 3's: 7,571 transitions at n_Q = 10^4 (3 Nov), two columns each (P6: old and new state).

Prints to the terminal only and writes no results file, so these numbers can never reach a figure or table.

    python scripts/probe_pqch_verify_many.py [--transitions 7571]
"""

import argparse
import time

import numpy as np

from veredact_bench.methods.veredact.crypto.pqch_sis import SISChameleonHash, default_params
from veredact_bench.utils.config import load


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--transitions", type=int, default=7571)
    args = ap.parse_args()
    cfg = load("experiment")
    ch_cfg = cfg["security"]["pqch"]
    ch = SISChameleonHash(
        default_params(n=ch_cfg["n"], k=ch_cfg["k"], sigma_R=ch_cfg["sigma_R"], sigma_g=ch_cfg["sigma_g"]),
        seed=cfg["meta"]["seed"],
    )
    pk, _ = ch.keygen()
    cols = 2 * args.transitions  # P6: PQCH.Hash(MR_b, r_b) and PQCH.Hash(MR_b', r_b') per transition
    msgs = [i.to_bytes(8, "big") * 4 for i in range(cols)]
    R = np.stack([ch.sample_r() for _ in range(cols)], axis=1)
    # setup, untimed: the hashes the audit checks against (one product, as the ledger built them)
    H = np.stack([ch.H(m) for m in msgs], axis=1)
    chs = [c.tobytes() for c in ((pk.mul_many(R) + H) % ch.p.q).astype(np.uint32).T]
    print(f"PROBE (never a result): {args.transitions} transitions = {cols} columns, n={ch.p.n} k={ch.p.k} M={ch.p.M}")

    t = time.perf_counter()
    ok_loop = [ch.verify(pk, chs[j], msgs[j], R[:, j]) for j in range(cols)]
    loop_s = time.perf_counter() - t

    t = time.perf_counter()
    ok_many = ch.verify_many(pk, chs, msgs, R)
    many_s = time.perf_counter() - t

    assert all(ok_loop) and ok_loop == ok_many, "verify_many disagrees with verify"
    print(f"PROBE loop of verify : {loop_s * 1000:10.1f} ms  ({loop_s * 1000 / cols:.3f} ms per column)")
    print(f"PROBE verify_many    : {many_s * 1000:10.1f} ms  ({many_s * 1000 / cols:.3f} ms per column)")
    print(f"PROBE batching factor: {loop_s / many_s:.2f}x  (implementation-plan.md section 6 assumed ~4x)")


if __name__ == "__main__":
    main()
