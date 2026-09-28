"""Experiments 0-5 of the VeRedact-PQ evaluation. Each writes results/<exp>.csv.

  exp0  Table VI  primitive execution times
  exp1  Fig. 3    redaction latency & throughput vs arrival rate; PQCH adaptations vs Zipf skew
  exp2  Fig. 4    authorization latency vs batch size and committee size (+ Re-ZK)
  exp3  Fig. 5    audit response generation time & size vs n_Q (+ Per-Record Evidence)
  exp4  Fig. 6    auditor verification time (normal/deep, PQ-adapted/classical) + fault injection
  exp5  Fig. 7    gas per authorization round and per redaction vs batch size (estimate; see gas_model)
"""
import copy
import json
import os
import random
import statistics
import time

from .baselines import EXP_BASELINES, SPECS, make_baseline
from .config import EXP1, EXP2, EXP3, EXP4, EXP5, D, RunConfig, threshold
from .crypto import hashing
from .env import make_crypto, make_ledger
from .gas_model import gas_of
from .metrics import CsvWriter, ci95, summarize
from .protocol.veredact import Rejection, VeRedactPQ
from .sim import Pipeline
from .workload import ZipfTargets, poisson_arrivals


def _variants(L):
    return {
        "VeRedact-PQ": lambda: VeRedactPQ(L.clone()),
        "Per-Request": lambda: VeRedactPQ(L.clone(), batching="none"),
        "Fixed-Batch": lambda: VeRedactPQ(L.clone(), batching="fixed", fixed_B=EXP1["fixed_batch"]),
        "No-BIMC": lambda: VeRedactPQ(L.clone(), bimc=False),
    }


def _timeit(fn, reps):
    ts = []
    for _ in range(reps):
        t = time.perf_counter()
        fn()
        ts.append((time.perf_counter() - t) * 1000)
    return statistics.median(ts)


# =================================================================== Exp. 0
def exp0(cfg: RunConfig):
    out = CsvWriter(os.path.join(cfg.out_dir, "exp0_primitives.csv"))
    L = make_ledger(512)
    c = L.c
    kp = c.keygen()
    msg = os.urandom(64)
    sig = c.sign(kp.sk, msg)
    reps = 50 if cfg.quick else 1000
    x = os.urandom(32)
    proof = c.zk.prove(L.zk_params, x, None, lambda *_: True)
    r = c.ch.sample_r()
    root, root2 = os.urandom(32), os.urandom(32)
    share = c.ch.part_adapt(L.td[1], root, r, root2)
    rows = [
        ("T_S", "ML-DSA-65 sign", lambda: c.sig.sign(kp.sk, msg)),
        ("T_V", "ML-DSA-65 verify", lambda: c.sig.verify(kp.pk, msg, sig)),
        ("T_ZP", "PQZK prove (simulated)", lambda: c.zk.prove(L.zk_params, x, None, lambda *_: True)),
        ("T_ZV", "PQZK verify (simulated)", lambda: c.zk.verify(L.zk_params, x, proof)),
        ("T_CH", "PQCH hash (stand-in)", lambda: c.ch.hash(L.pk_ch, root, r)),
        ("T_PA", "PQCH partial adapt (stand-in)", lambda: c.ch.part_adapt(L.td[1], root, r, root2)),
        ("T_CB", "PQCH combine t shares (stand-in)", lambda: c.ch.combine([share] * L.t, r)),
        ("T_H", "SHA3-256 (64-byte input)", lambda: hashing.H(msg)),
        ("T_PRF", "HMAC-SHA3-256", lambda: hashing.PRF(L.K_idx, msg)),
    ]
    for sym, inst, fn in rows:
        n = min(reps, 20) if sym == "T_ZP" else reps
        out.add(symbol=sym, instantiation=inst, median_ms=_timeit(fn, n), reps=n)
    out.add(symbol="|sigma|", instantiation=c.sig.name, median_ms=float(c.sig.sig_size), reps=0)
    out.save()


# =================================================================== Exp. 1
def exp1(cfg: RunConfig):
    out = CsvWriter(os.path.join(cfg.out_dir, "exp1_throughput_latency.csv"))
    duration = 2.0 if cfg.quick else EXP1["duration_s"]
    rates = EXP1["rates"][:2] if cfg.quick else EXP1["rates"]
    for rep in range(1 if cfg.quick else cfg.reps):
        L = make_ledger(cfg.ledger_size, seed=rep)
        schemes = dict(_variants(L))
        for key in EXP_BASELINES[1]:
            schemes[SPECS[key].label] = (lambda k=key: make_baseline(k, L.clone()))
        # (a)(b): arrival-rate sweep at default skew
        for rate in rates:
            arrivals = poisson_arrivals(rate, duration, seed=rep)
            for name, mk in schemes.items():
                sch = mk()
                res = Pipeline(sch, ZipfTargets(sch.L, D.zipf_s, seed=rep), rate, D.block_period_s,
                               D.net_latency_ms, D.vps_workers).run(arrivals).results(duration)
                out.add(sweep="rate", rep=rep, scheme=name, rate=rate, zipf=D.zipf_s,
                        throughput=res["throughput"], finalized=res["finalized"], rejected=res["rejected"],
                        adapt_per_1000=res["adapt_per_1000"], **summarize(res["latencies"], "lat_"))
        # (c): Zipf sweep at fixed rate
        rate = EXP1["zipf_rate"] if not cfg.quick else rates[-1]
        arrivals = poisson_arrivals(rate, duration, seed=rep)
        for s in EXP1["zipf"]:
            for name, mk in schemes.items():
                sch = mk()
                res = Pipeline(sch, ZipfTargets(sch.L, s, seed=rep), rate, D.block_period_s,
                               D.net_latency_ms, D.vps_workers).run(arrivals).results(duration)
                out.add(sweep="zipf", rep=rep, scheme=name, rate=rate, zipf=s, throughput=res["throughput"],
                        finalized=res["finalized"], adapt_per_1000=res["adapt_per_1000"],
                        **summarize(res["latencies"], "lat_"))
    out.save()


# =================================================================== Exp. 2
def _validated(v, targets, m):
    vrs = []
    while len(vrs) < m:
        r = v.validate(v.make_request(len(vrs) % 16, targets.pick(), b"red-%d" % len(vrs)))
        if not isinstance(r, Rejection) and all(x.req.TID != r.req.TID for x in vrs):
            vrs.append(r)
    return vrs


def exp2(cfg: RunConfig):
    out = CsvWriter(os.path.join(cfg.out_dir, "exp2_authorization.csv"))
    committees = EXP2["committee"][:3] if cfg.quick else EXP2["committee"]
    sizes = EXP2["batch_sizes"][:4] if cfg.quick else EXP2["batch_sizes"]
    for n in committees:
        t = threshold(n)
        L = make_ledger(min(cfg.ledger_size, 16_384), n=n, t=t)
        for m in sizes:
            if n != D.n and m != 64:
                continue  # (a) batch sweep at default n; (b) committee sweep at m = 64
            for rep in range(cfg.reps):
                for name, kw in [("VeRedact-PQ", {}), ("Re-ZK", {"rezk": True})]:
                    v = VeRedactPQ(L.clone(), **kw)
                    batch = _validated(v, ZipfTargets(v.L, 0.0, seed=rep), m)
                    v.c.reset()
                    t0 = time.perf_counter()
                    v.authorize(batch)
                    ms = (time.perf_counter() - t0) * 1000
                    counts, times = v.c.snapshot()
                    out.add(scheme=name, n=n, t=t, m=m, rep=rep, batch_ms=ms, per_request_ms=ms / m,
                            attest_ms=times.get("T_V", 0) * m / max(1, counts.get("T_V", 1)),
                            zk_ms=times.get("T_ZV", 0), committee_sign_ms=times.get("T_S", 0),
                            **{f"cnt_{k}": val for k, val in counts.items()})
                for key in EXP_BASELINES[2]:
                    b = make_baseline(key, L.clone())
                    tg = ZipfTargets(b.L, 0.0, seed=rep)
                    reqs = [b.make_request(i % 16, tg.pick(), b"r%d" % i) for i in range(m)]
                    b.c.reset()
                    t0 = time.perf_counter()
                    for R in reqs:
                        b.authorize(R)
                    ms = (time.perf_counter() - t0) * 1000
                    out.add(scheme=SPECS[key].label, n=n, t=t, m=m, rep=rep, batch_ms=ms, per_request_ms=ms / m,
                            **{f"cnt_{k}": val for k, val in b.c.snapshot()[0].items()})
    out.save()


# =================================================================== Exp. 3 / 4 helpers
def populate_veredact(L, total, per_batch, seed=0):
    """Create `total` finalized redactions grouped `per_batch` per ABRRR authorization batch."""
    v = VeRedactPQ(L.clone())
    tg = ZipfTargets(v.L, D.zipf_s, seed=seed)
    while len(v.records) < total:
        batch = _validated(v, tg, min(per_batch, total - len(v.records)))
        auth = v.authorize(batch)
        if auth:
            v.execute(auth)
    v.index_records()
    return v


def populate_baseline(key, L, total, seed=0, classical=False):
    b = make_baseline(key, L.clone(), pq_adapted=not classical)
    tg = ZipfTargets(b.L, D.zipf_s, seed=seed)
    i = 0
    while len(b.records) < total:
        b.process(b.make_request(i % 16, tg.pick(), b"r%d" % i))
        i += 1
    return b


def _nq(cfg, key):
    return [n for n in (EXP3 if key == 3 else EXP4)["n_Q"] if not cfg.quick or n <= 100]


# =================================================================== Exp. 3
def exp3(cfg: RunConfig):
    out = CsvWriter(os.path.join(cfg.out_dir, "exp3_audit_efficiency.csv"))
    nqs = _nq(cfg, 3)
    L = make_ledger(cfg.ledger_size)
    for k in EXP3["records_per_batch"]:
        v = populate_veredact(L, max(nqs), k)
        for n_Q in nqs:
            recs = v.records[:n_Q]
            for name, per_record in [("VeRedact-PQ", False), ("Per-Record Evidence", True)]:
                v.per_record = per_record
                ts = []
                for _ in range(cfg.reps):
                    t0 = time.perf_counter()
                    resp = v.audit(recs)
                    ts.append((time.perf_counter() - t0) * 1000)
                out.add(scheme=name, records_per_batch=k, n_Q=n_Q, resp_bytes=resp.nbytes, **summarize(ts, "gen_ms_"))
            v.per_record = False
    for key in EXP_BASELINES[3]:
        b = populate_baseline(key, L, max(nqs))
        for n_Q in nqs:
            ts = []
            for _ in range(cfg.reps):
                t0 = time.perf_counter()
                resp = b.audit(b.records[:n_Q])
                ts.append((time.perf_counter() - t0) * 1000)
            out.add(scheme=SPECS[key].label, records_per_batch="-", n_Q=n_Q, resp_bytes=resp["nbytes"],
                    **summarize(ts, "gen_ms_"))
    out.save()


# =================================================================== Exp. 4
def _tamper(records, frac, rng):
    """Copy records and corrupt a fraction: modified (D'), substituted (other record's PBRP), stale (version)."""
    recs = [copy.copy(r) for r in records]
    bad = set()
    for i in rng.sample(range(len(recs)), max(1, int(frac * len(recs)))):
        r, kind = recs[i], rng.choice(["modified", "substituted", "stale"])
        if kind == "modified":
            r.D_new = hashing.H("forged", r.D_new)
        elif kind == "substituted":
            r.h_pbrp = recs[(i + 1) % len(recs)].h_pbrp
        else:
            r.v_b_new = r.v_b_new - 1
        bad.add(r.RID)
    return recs, bad


def exp4(cfg: RunConfig):
    out = CsvWriter(os.path.join(cfg.out_dir, "exp4_verification.csv"))
    nqs = _nq(cfg, 4)
    L = make_ledger(cfg.ledger_size)
    v = populate_veredact(L, max(nqs), 16)
    for n_Q in nqs:
        resp = v.audit(v.records[:n_Q])
        for level in EXP4["levels"]:
            ts, br = [], None
            for _ in range(cfg.reps):
                v.c.reset()
                t0 = time.perf_counter()
                v.verify_audit(resp, deep=(level == "deep"))
                ts.append((time.perf_counter() - t0) * 1000)
                br = v.c.snapshot()[1]
            out.add(scheme="VeRedact-PQ", instantiation="PQ", level=level, n_Q=n_Q, **summarize(ts, "ver_ms_"),
                    **{f"ms_{k}": val for k, val in br.items()})
    rng = random.Random(0)
    for frac in EXP4["inject"]:  # verification granularity
        recs, bad = _tamper(v.records[:max(nqs)], frac, rng)
        res = v.verify_audit(v.audit(recs))
        rej = sum(1 for rid in bad if not res[rid]) / len(bad)
        kept = sum(1 for rid, ok in res.items() if rid not in bad and ok) / (len(res) - len(bad))
        out.add(scheme="VeRedact-PQ", instantiation="PQ", level="inject", n_Q=len(recs), inject=frac,
                invalid_rejected=rej, valid_retained=kept)
    for classical in (False, True):
        Lb = L if not classical else make_ledger(cfg.ledger_size, classical=True)
        for key in EXP_BASELINES[4]:
            b = populate_baseline(key, Lb, max(nqs), classical=classical)
            for n_Q in nqs:
                resp = b.audit(b.records[:n_Q])
                ts = []
                for _ in range(cfg.reps):
                    t0 = time.perf_counter()
                    b.verify_audit(resp)
                    ts.append((time.perf_counter() - t0) * 1000)
                out.add(scheme=SPECS[key].label, instantiation="classical" if classical else "PQ-adapted",
                        level="normal", n_Q=n_Q, **summarize(ts, "ver_ms_"))
    out.save()


# =================================================================== Exp. 5
def exp5(cfg: RunConfig):
    out = CsvWriter(os.path.join(cfg.out_dir, "exp5_gas.csv"))
    L = make_ledger(cfg.ledger_size)
    chainlog = [{"label": "setup", "ops": L.chain.ops}]
    setup_gas = gas_of(L.chain.ops, phases={1})
    out.add(scheme="VeRedact-PQ", op="setup (policies+committee)", m=0, zipf="-", gas_total=setup_gas, gas_per_redaction=0.0)
    for s in EXP5["zipf"]:
        for m in EXP5["batch_sizes"]:
            v = VeRedactPQ(L.clone())
            start = len(v.L.chain.ops)
            batch = _validated(v, ZipfTargets(v.L, s, seed=m), m)
            auth = v.authorize(batch)
            rrs = v.execute(auth)
            v.index_records(rrs)
            ops = v.L.chain.ops[start:]
            g = gas_of(ops)
            trans = sum(o.get("transitions", 0) for o in ops)
            out.add(scheme="VeRedact-PQ", op="authorization round", m=m, zipf=s, transitions=trans,
                    gas_total=g, gas_per_redaction=g / len(rrs))
            chainlog.append({"label": f"VeRedact-PQ m={m} s={s}", "ops": ops})
            for key in EXP_BASELINES[5]:
                b = make_baseline(key, L.clone())
                start = len(b.L.chain.ops)
                tg = ZipfTargets(b.L, s, seed=m)
                done = sum(1 for i in range(m) if b.process(b.make_request(i % 16, tg.pick(), b"r%d" % i)))
                g = gas_of(b.L.chain.ops[start:])
                chainlog.append({"label": f"{SPECS[key].label} m={m} s={s}", "ops": b.L.chain.ops[start:]})
                out.add(scheme=SPECS[key].label, op="authorization round", m=m, zipf=s, transitions=done,
                        gas_total=g, gas_per_redaction=g / max(1, done))
    out.save()
    with open(os.path.join(cfg.out_dir, "exp5_chainlog.json"), "w") as f:
        json.dump(chainlog, f, default=str)


ALL = {"exp0": exp0, "exp1": exp1, "exp2": exp2, "exp3": exp3, "exp4": exp4, "exp5": exp5}
