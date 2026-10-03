"""exp00 — primitive timings (manuscript tab:primitives), one results folder per method.

One row per (symbol, instantiation, rep). VeRedact-PQ primitives run on the same Crypto facade the
protocol uses (ML-DSA-65, winterfell STARK with the policy predicates, distributed SIS-PQCH, SHA3-256,
HMAC-SHA3-256); baseline primitives run on each baseline's own construction module at the parameters in
[baselines.*]. Inputs are fresh per repetition; setup (keys, DKG, registries) is untimed.
"""
import hashlib
import os
import importlib
import time

from veredact_bench.methods.veredact.crypto import Crypto


def _mod(package: str):
    return importlib.import_module(f"veredact_bench.methods.baselines.{package}.construction")


def _time(fn, reps: int):
    out = []
    for _ in range(reps):
        if isinstance(fn, _SelfTimed):
            out.append(fn())
            continue
        arg = fn.prepare() if isinstance(fn, _Op) else None
        t = time.perf_counter()
        fn(arg) if isinstance(fn, _Op) else fn()
        out.append((time.perf_counter() - t) * 1000)
    return out


class _Op:
    """run(prepared) timed; prepare() untimed (fresh inputs per repetition)."""

    def __init__(self, prepare, run):
        self.prepare, self.run = prepare, run

    def __call__(self, arg):
        return self.run(arg)


class _SelfTimed:
    """fn() returns its own milliseconds (for operations interleaved with untimed work)."""

    def __init__(self, fn):
        self.fn = fn

    def __call__(self):
        return self.fn()


def veredact_ops(cfg):
    c = Crypto(cfg, cfg["dataset"]["requesters"])
    kp = c.keygen()
    n, t = cfg["veredact"]["committee_n"], cfg["veredact"]["committee_t"]
    pk_ch, td = c.ch.dkeygen(n, t)
    thr, now = cfg["security"]["pqzk"]["attribute_levels"], int(time.time())
    key = os.urandom(cfg["security"]["prf_key_bits"] // 8)
    sig = c.sign(kp.sk, b"m")
    x = os.urandom(32)
    proof = c.zk.prove(0, x, thr, now)

    def begin():
        return c.ch.begin_adapt(pk_ch, os.urandom(32), c.ch.sample_r(), os.urandom(32))

    def combine_ms():  # combiner side: perturbation + G-sampling (begin_adapt) and combination; shares untimed
        t0 = time.perf_counter()
        pert, z = begin()
        t1 = time.perf_counter()
        deltas = [c.ch.part_adapt(td[k], z) for k in range(1, t + 1)]
        t2 = time.perf_counter()
        c.ch.combine(pert, z, deltas)
        return ((t1 - t0) + (time.perf_counter() - t2)) * 1000

    return [
        ("T_S", "ML-DSA-65 sign", lambda: c.sig.sign(kp.sk, os.urandom(32))),
        ("T_V", "ML-DSA-65 verify", lambda: c.sig.verify(kp.pk, b"m", sig)),
        ("T_ZP", "PQZK STARK prove (membership + expiry + attribute)", lambda: c.zk.prove(0, os.urandom(32), thr, now)),
        ("T_ZV", "PQZK STARK verify", lambda: c.zk.verify(0, x, proof, thr, now)),
        ("T_CH", "PQCH (SIS) hash", lambda: c.ch.hash(pk_ch, os.urandom(32), c.ch.sample_r())),
        ("T_PA", "PQCH partial adapt (one member)", _Op(begin, lambda pz: c.ch.part_adapt(td[1], pz[1]))),
        ("T_CB", f"PQCH combine: perturbation + G-sampling + {t} shares", _SelfTimed(combine_ms)),
        ("T_H", "SHA3-256 (64-byte input)", lambda: hashlib.sha3_256(os.urandom(64)).digest()),
        ("T_PRF", "HMAC-SHA3-256", lambda: c.PRF(key, os.urandom(32))),
    ]


def _ecdsa_op():
    from coincurve import PrivateKey
    sk = PrivateKey()
    msg = os.urandom(32)
    s = sk.sign(msg)
    return ("T_V^c", "ECDSA secp256k1 verify (transaction signatures)", lambda: sk.public_key.verify(s, msg))


def s01_ops(cfg):
    import gmpy2
    from cryptography.hazmat.primitives.asymmetric import rsa
    ops = [_ecdsa_op()]
    # ---- [1] Improved DCH on BLS12-381, RSA accumulator ------------------------------------------------
    s1 = _mod("s01_improved_dch")
    b1 = cfg["baselines"]["S1"]
    key = s1.dkg(b1["threshold_t"], b1["nodes_n"])
    dch = s1.ImprovedDCH(key)
    parties = list(key.shares)[: b1["threshold_t"]]
    lam = s1.lagrange_at_zero(parties)
    hv = dch.hash(b"m")
    ops.append(("T_PA^c", "Improved DCH partial collision, BLS12-381 [1]",
                lambda: dch.partial(parties[0], lam[parties[0]], b"m", os.urandom(32))))
    parts = [dch.partial(i, lam[i], b"m", b"m2") for i in parties]

    def s1_combine():
        out = hv.r
        for p in parts:
            out = out + p
        return out
    ops.append(("T_CB^c", "Improved DCH share combination [1]", s1_combine))
    ops.append(("T_CV^c", "Improved DCH verify (2 pairings) [1]", lambda: dch.verify(b"m", hv.r, hv.h)))

    N = rsa.generate_private_key(public_exponent=65537, key_size=b1["accumulator_rsa_bits"]).private_numbers().public_numbers.n
    g = pow(3, 2, N)
    primes = [int(gmpy2.next_prime(int.from_bytes(os.urandom(32), "big") | 1)) for _ in range(64)]
    u = 1
    for p in primes:
        u *= p
    acc = int(gmpy2.powmod(g, u, N))
    x = int(gmpy2.next_prime(int.from_bytes(os.urandom(32), "big") | 1))
    _, a_, b_ = gmpy2.gcdext(u, x)
    B = gmpy2.powmod(g, b_, N)
    ops.append(("T_Acc", f"RSA-{b1['accumulator_rsa_bits']} accumulator non-membership verify [1]",
                lambda: gmpy2.powmod(acc, a_, N) * gmpy2.powmod(B, x, N) % N == g))
    return ops


def s13_ops(cfg):
    import gmpy2
    s13 = _mod("s13_eaq_vrbc")
    b13 = cfg["baselines"]["S13"]
    p = s13.setup(b13["rsa_bits"], b13["miners"], b13["l_bits"])
    blk = s13.upload_block(p, 0, b"genesis", [os.urandom(16) for _ in range(cfg["dataset"]["leaves_per_batch"])])
    tag, _, _ = s13.tag_gen(p, 0, blk.h())
    txs_new = [os.urandom(16) for _ in range(cfg["dataset"]["leaves_per_batch"])]
    return [
        ("T_AD^c", f"double-trapdoor CH collision incl. MHT, RSA-{b13['rsa_bits']} [13]",
         lambda: s13.redact_block(p, blk, txs_new)),
        ("T_CV^c", f"double-trapdoor CH verify, RSA-{b13['rsa_bits']} [13]", lambda: s13.ch_verify(p, blk)),
        ("T_Tag", f"identity-based tag generation, RSA-{b13['rsa_bits']} [13]", lambda: s13.tag_gen(p, 0, blk.h())),
        ("T_Tag", f"identity-based tag verification, RSA-{b13['rsa_bits']} [13]",
         lambda: s13.tag_verify(p, 0, blk.h(), tag)),
        ("T_E^c", f"modular exponentiation, RSA-{b13['rsa_bits']} full exponent [13]",
         lambda: gmpy2.powmod(p.g, p.d, p.N)),
    ]


def s27_ops(cfg):
    s27 = _mod("s27_etch")
    b27 = cfg["baselines"]["S27"]
    keys = s27.keygen(b27["threshold_t"], b27["redactors_n"])
    signers = list(keys.parts)[: b27["threshold_t"]]
    v = s27.hash_(keys.Y, b"m")
    lam27 = s27.lagrange(signers)

    def s27_partial():  # one redactor: K_i = g^{k_i}; r' = h / K; e' = H(m', r'); w_i = k_i - e' lambda_i s_i
        k = s27.rand()
        Ki = s27.gmul(k)
        r_new = s27.add(v.h, s27.neg(Ki))
        e_new = s27.Hs(b"m2", r_new)
        return (k - e_new * lam27[signers[0]] * keys.parts[signers[0]].s) % s27.N
    Ks = [s27.gmul(s27.rand()) for _ in signers]
    ws = [s27.rand() for _ in signers]
    return [
        _ecdsa_op(),
        ("T_PA^c", "ETCH Adapt, one redactor, secp256k1 [27]", s27_partial),
        ("T_CB^c", "ETCH Adapt, commitment aggregator [27]", lambda: (s27.add(*Ks), sum(ws) % s27.N)),
        ("T_CV^c", "ETCH Verify, secp256k1 [27]", lambda: s27.verify(keys.Y, b"m", v)),
    ]


def s34_ops(cfg):
    s34 = _mod("s34_rebs")
    b34 = cfg["baselines"]["S34"]
    amc = s34.gpgen(b34["rsa_bits"])
    l, tt = b34["policy_attributes"], b34["policy_threshold"]
    avns = [s34.key_avn() for _ in range(l)]
    pol = s34.Policy(s34.lsss_threshold(l, tt), [s34.rnd() for _ in range(l)], tt)
    chv, p_t, q_t = s34.chash(amc, avns, pol, b"tx", 1, b34["rsa_bits"])
    trap = p_t.to_bytes(b34["rsa_bits"] // 16 + 8, "big") + q_t.to_bytes(b34["rsa_bits"] // 16 + 8, "big")
    k_tr, sig_amc = s34.key_tr(amc, b"TR0")
    akeys = {i: s34.attr_keygen(amc, avns[i], b"TR0", sig_amc, pol.values[i]) for i in range(l)}
    return [
        ("T_Pol", f"MA-ABE Info_Trap decryption, t={tt} of l={l}, BLS12-381 [34]",
         lambda: s34.recover_trap(pol, chv.info, b"TR0", akeys)),
        ("T_AD^c", f"CHET ChCld, RSA-{b34['rsa_bits']} [34]", lambda: s34.chcld(amc, k_tr, trap, chv, os.urandom(32))),
        ("T_CV^c", f"CHET ChVer, RSA-{b34['rsa_bits']} [34]", lambda: s34.chver(amc, b"tx", chv)),
    ]


OPS = {"veredact": veredact_ops, "S1": s01_ops, "S13": s13_ops, "S27": s27_ops, "S34": s34_ops}


def run(cfg, out):
    x = cfg["experiment"]
    for key in x["systems"]:
        if not out.begin(key):
            continue
        for symbol, inst, fn in OPS[key](cfg):  # setup (keys, DKG, registries) untimed
            for sample, ms in enumerate(_time(fn, x["samples_per_point"])):
                out.row(experiment=x["id"], system=key, symbol=symbol, instantiation=inst, sample=sample, ms=ms)
            out.log.info(f"  {key:8s} {symbol:7s} {inst}")
        out.end()
