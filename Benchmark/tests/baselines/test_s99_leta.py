import numpy as np

from veredact_bench.methods.baselines.s99_leta.construction import (
    N,
    Params,
    Q,
    agg_verify,
    aggregate,
    intt,
    matvec,
    ntt,
    register,
    setup,
    sign,
    vpd_leaf,
    vpd_root,
    zkp_verify,
)

P = Params(k=2, tau=39, sigma_s=2.0, gamma=1 << 17)  # small rank: test speed; the ring is the real one


def _schoolbook(a, b):
    c = [0] * N
    for i in range(N):
        for j in range(N):
            if a[i] and b[j]:
                k, v = (i + j) % N, int(a[i]) * int(b[j])
                c[k] = (c[k] + (v if i + j < N else -v)) % Q  # x^n = -1
    return np.array(c, dtype=np.int64)


def test_ntt_is_negacyclic_multiplication():
    rng = np.random.default_rng(1)
    a, b = rng.integers(0, Q, N), np.zeros(N, dtype=np.int64)
    b[[0, 5, N - 1]] = [3, Q - 1, 7]  # sparse: the schoolbook product stays fast
    assert np.array_equal(intt(ntt(a)), a % Q)
    assert np.array_equal(intt(ntt(a) * ntt(b) % Q), _schoolbook(a, b))


def test_inverse_matrix():
    S = setup(P, b"seed")
    prod = np.stack([matvec(S.Ah, S.Ainv_h[:, j, :]) for j in range(P.k)], axis=1)  # A A^{-1}, NTT domain
    eye = np.eye(P.k, dtype=np.int64)[:, :, None] * np.ones(N, dtype=np.int64)  # NTT(1) = all ones
    assert np.array_equal(prod, eye)


def test_sign_zkp_verify_and_rejections():
    S = setup(P, b"seed")
    v = register(S, b"V0")
    sig = sign(S, v, b"m")
    assert zkp_verify(S, v.b, b"m", sig)
    assert not zkp_verify(S, v.b, b"other", sig)  # Eq. 15: c' != c
    sig.r[0, 0] = (sig.r[0, 0] + 1) % Q
    assert not zkp_verify(S, v.b, b"m", sig)  # Eq. 14: mu' != mu


def _platoon(S, vs, forged=None):
    sigs = []
    for i, v in enumerate(vs):
        s = sign(S, v, b"m%d" % i)
        if i == forged:
            s.r[1, 3] = (s.r[1, 3] + 1) % Q
        sigs.append(s)
    leaves = [vpd_leaf(v.pseudonym, s, b"\0" * 32, 1) for v, s in zip(vs, sigs)]
    members = [(v.pseudonym, 1, s.mu) for v, s in zip(vs, sigs)]
    agg = aggregate(S, sigs, members, vpd_root(leaves), 100)
    return agg, members, [s.mu for s in sigs], [v.b for v in vs], [s.c for s in sigs]


def test_aggregate_verifies_and_rejects_forgery_and_stale():
    S = setup(P, b"seed")
    vs = [register(S, b"V%d" % i) for i in range(5)]  # odd: the VPD-Tree pads a level
    assert agg_verify(S, *_platoon(S, vs), now=110, dt=30)
    assert not agg_verify(S, *_platoon(S, vs), now=200, dt=30)  # T - T5 > dT
    assert not agg_verify(S, *_platoon(S, vs, forged=2), now=110, dt=30)  # one bad vehicle fails the platoon
