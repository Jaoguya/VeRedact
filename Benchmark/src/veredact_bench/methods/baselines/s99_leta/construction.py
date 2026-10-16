"""S99 = Q. Li, Y. Xia, X. Liu, X. Chen, Z. Liu, Z. Guo, Z. Liu, L. Fang, "LETA: A Lattice-Based Efficient and
Traceable Privacy-Preserving Batch Authentication Scheme for Vehicle Platoon in VANETs", IEEE JSAC 44, 2026
(Reference/S99_Li2026_LETA/S99_fulltext_pdftotext.md, Sec. IV).

Implements the paper's module-lattice construction over R_q = Z_q[x]/(x^n + 1):
  * registration   s = (s1, s2) <- D_{R,s};  b = A s1 + s2 mod q                       (Eqs. 4-5)
  * Sign / ZKP     mu = A z1 + z2;  c = h2(b || mu || m);  r = (z1 + c s1) + A^{-1}(z2 + c s2)   (Eqs. 6-8)
                   Sign_Vi = (r, c), Z_Vi = (mu, r, c)
  * ZKP verify     mu' = A r - c b == mu  and  c' = h2(b || mu || m) == c               (Eqs. 14-15)
  * VPD-Tree       leaves Hash_Vi = h1(P_Vi || r_i || eta_i || T2), parents h1(left || right),
                   Root = VP identity (Eq. 9)
  * Aggregate      (beta_1..beta_n) = h2(alpha_1, t_1, mu_1, ..., VP identity); c_agg = sum beta_i c_i,
                   r_agg = sum beta_i r_i                                                (Eqs. 10-12)
  * AggVerify      A r_agg == sum beta_i (mu_i + c_i b_i) mod q                          (Eq. 13)
Correctness: A r = A z1 + z2 + c (A s1 + s2) = mu + c b, so Eq. 13 holds term by term (paper Sec. V-A).

Instantiation (the paper fixes no concrete n, q, k, l, widths; every value is in configs/methods/s99_leta.yaml):
  * ring of FIPS 204 (ML-DSA): n = 256, q = 8,380,417, NTT with zeta = 1753, so one polynomial product is two
    forward NTTs, a pointwise product and one inverse NTT (the paper's T_m).
  * A must be square (k = l): r = r1 + A^{-1} r2 needs A^{-1} (the paper writes A in R_q^{k x l} and uses A^{-1}).
    A^{-1} is computed once per system, slot by slot in the NTT domain.
  * h2 -> B: ML-DSA SampleInBall (tau coefficients in {-1, +1}); h0 -> R_q: SHAKE-128 rejection sampling;
    h1 -> its 32-byte SHAKE-256 digest (the paper maps it into a short ring element; the tree only compares
    and re-hashes digests, so the cost is the same).
  * As in the paper, Sign has no rejection sampling and AggVerify does not recompute the c_i: both are the
    paper's construction, reproduced as written (it is the paper's security claim, not ours).
"""

import hashlib
import os
import secrets
from dataclasses import dataclass

import numpy as np

Q = 8380417  # FIPS 204 modulus: q = 2^23 - 2^13 + 1, q = 1 mod 512 (NTT-friendly for n = 256)
N = 256
ZETA = 1753  # primitive 512-th root of unity mod q (FIPS 204)


def _brv8(k: int) -> int:
    return int(f"{k:08b}"[::-1], 2)


ZETAS = np.array([pow(ZETA, _brv8(k), Q) for k in range(N)], dtype=np.int64)
N_INV = pow(N, Q - 2, Q)


# ----------------------------------------------------------------------------------------- ring arithmetic
def ntt(a: np.ndarray) -> np.ndarray:
    """Negacyclic NTT of every length-256 row of a (any leading shape), FIPS 204 Alg. 41, vectorized per level."""
    a = np.array(a, dtype=np.int64) % Q
    lead = a.shape[:-1]
    L = 128
    while L >= 1:
        nb = N // (2 * L)
        blk = a.reshape(*lead, nb, 2, L)
        z = ZETAS[nb : 2 * nb].reshape(nb, 1)
        t = (blk[..., 1, :] * z) % Q
        lo = blk[..., 0, :]
        blk = np.stack(((lo + t) % Q, (lo - t) % Q), axis=-2)
        a = blk.reshape(*lead, N)
        L //= 2
    return a


def intt(a: np.ndarray) -> np.ndarray:
    """Inverse of ntt() (FIPS 204 Alg. 42), coefficients in [0, q)."""
    a = np.array(a, dtype=np.int64) % Q
    lead = a.shape[:-1]
    L = 1
    while L < N:
        nb = N // (2 * L)
        blk = a.reshape(*lead, nb, 2, L)
        z = (-ZETAS[2 * nb - 1 - np.arange(nb)] % Q).reshape(nb, 1)
        lo, hi = blk[..., 0, :], blk[..., 1, :]
        blk = np.stack(((lo + hi) % Q, ((lo - hi) * z) % Q), axis=-2)
        a = blk.reshape(*lead, N)
        L *= 2
    return (a * N_INV) % Q


def matvec(Ah: np.ndarray, vh: np.ndarray) -> np.ndarray:
    """(k x l x n) @ (l x n) in the NTT domain -> (k x n)."""
    return (Ah * vh[np.newaxis, :, :] % Q).sum(axis=1) % Q


def centered(a: np.ndarray) -> np.ndarray:
    a = np.asarray(a, dtype=np.int64) % Q
    return np.where(a > Q // 2, a - Q, a)


def _mat_inverse(Ah: np.ndarray) -> np.ndarray:
    """Inverse of the k x k matrix A over R_q: in the NTT domain R_q splits into n copies of Z_q, so A^{-1} is
    n independent k x k inverses over Z_q (Gauss-Jordan). Raises if A is singular in some slot."""
    k = Ah.shape[0]
    inv = np.zeros_like(Ah)
    for s in range(N):
        M = [[int(Ah[i, j, s]) for j in range(k)] + [int(i == j) for j in range(k)] for i in range(k)]
        for c in range(k):
            p = next((r for r in range(c, k) if M[r][c] % Q), None)
            if p is None:
                raise ValueError("A is singular in an NTT slot")
            M[c], M[p] = M[p], M[c]
            f = pow(M[c][c], Q - 2, Q)
            M[c] = [x * f % Q for x in M[c]]
            for r in range(k):
                if r != c and M[r][c]:
                    g = M[r][c]
                    M[r] = [(x - g * y) % Q for x, y in zip(M[r], M[c])]
        for i in range(k):
            for j in range(k):
                inv[i, j, s] = M[i][k + j]
    return inv


# ----------------------------------------------------------------------------------------- hash functions
def _shake(data: bytes, nbytes: int, xof=hashlib.shake_256) -> bytes:
    return xof(data).digest(nbytes)


def h0(data: bytes) -> np.ndarray:
    """h0: {0,1}* -> R_q (Eq. 1): SHAKE-128, 23-bit rejection sampling (FIPS 204 RejNTTPoly)."""
    out, buf, i, need = [], b"", 0, N
    ctr = 0
    while len(out) < need:
        if i + 3 > len(buf):
            buf = _shake(data + ctr.to_bytes(2, "little"), 3 * (need + 32), hashlib.shake_128)
            ctr, i = ctr + 1, 0
        v = int.from_bytes(buf[i : i + 3], "little") & 0x7FFFFF
        i += 3
        if v < Q:
            out.append(v)
    return np.array(out, dtype=np.int64)


def h1(data: bytes) -> bytes:
    """h1: {0,1}* -> short ring element (Eq. 2), kept as its 32-byte SHAKE-256 seed (VPD-Tree nodes)."""
    return _shake(b"LETA-h1" + data, 32)


def sample_in_ball(seed: bytes, tau: int) -> np.ndarray:
    """h2: {0,1}* -> B (Eq. 3): tau coefficients in {-1, +1}, the rest 0 (FIPS 204 SampleInBall)."""
    stream = _shake(seed, 8 + 4 * tau + 64)
    signs = int.from_bytes(stream[:8], "little")
    c = np.zeros(N, dtype=np.int64)
    pos = 8
    for i in range(N - tau, N):
        while True:
            if pos >= len(stream):
                stream += _shake(seed + len(stream).to_bytes(4, "little"), 64)
            j = stream[pos]
            pos += 1
            if j <= i:
                break
        c[i] = c[j]
        c[j] = 1 - 2 * (signs & 1)
        signs >>= 1
    return c % Q


def _b(*parts) -> bytes:
    return b"".join(p if isinstance(p, bytes) else np.ascontiguousarray(p, dtype=np.int64).tobytes() for p in parts)


def h2(tau: int, *parts) -> np.ndarray:
    return sample_in_ball(b"LETA-h2" + _b(*parts), tau)


# ----------------------------------------------------------------------------------------- the scheme
@dataclass(frozen=True)
class Params:
    k: int  # module rank (A is k x k: A^{-1} is required by Eq. 8)
    tau: int  # weight of h2 outputs (challenges c_i, coefficients beta_i)
    sigma_s: float  # width of D_{R,s} for s1, s2
    gamma: int  # z1, z2 coefficients uniform in [-gamma, gamma] ("small", Eq. 6)


@dataclass
class System:
    p: Params
    Ah: np.ndarray  # A in the NTT domain (k x k x n)
    Ainv_h: np.ndarray  # A^{-1} in the NTT domain


@dataclass
class Vehicle:
    s1h: np.ndarray  # NTT domain
    s2h: np.ndarray
    b: np.ndarray  # public key b_Vi = A s1 + s2 mod q, coefficients
    bh: np.ndarray  # NTT domain
    pseudonym: bytes  # P_Vi = R_Vi xor h0(theta_Vi)


@dataclass
class Signature:
    r: np.ndarray  # k x n coefficients (Sign_Vi = (r, c))
    c: np.ndarray  # n coefficients
    mu: np.ndarray  # k x n commitment (Z_Vi = (mu, r, c))


def setup(p: Params, seed: bytes | None = None) -> System:
    """TA: A <- R_q^{k x k} uniform (sampled directly in the NTT domain, as FIPS 204 ExpandA), A^{-1} once."""
    seed = seed or os.urandom(32)
    while True:
        Ah = np.stack([np.stack([h0(seed + bytes([i, j])) for j in range(p.k)]) for i in range(p.k)])
        try:
            return System(p, Ah, _mat_inverse(Ah))
        except ValueError:
            seed = hashlib.sha3_256(seed).digest()


def _gauss(rng, sigma, shape):
    return np.rint(rng.normal(0.0, sigma, size=shape)).astype(np.int64)


def register(S: System, identity: bytes, rng=None) -> Vehicle:
    """Vehicle registration (Sec. IV-B1): R_Vi = h0(ID || N || s) is bound to a TA pseudonym; keys from D_{R,s}."""
    rng = rng or np.random.default_rng(secrets.randbits(64))
    k = S.p.k
    s1, s2 = _gauss(rng, S.p.sigma_s, (k, N)), _gauss(rng, S.p.sigma_s, (k, N))
    s1h, s2h = ntt(s1), ntt(s2)
    bh = (matvec(S.Ah, s1h) + s2h) % Q
    R_v = h0(identity + _b(s1, s2))
    theta = _gauss(rng, S.p.sigma_s, N)
    pseudonym = hashlib.sha3_256(_b((R_v ^ h0(_b(theta))) % Q)).digest()
    return Vehicle(s1h, s2h, intt(bh), bh, pseudonym)


def sign(S: System, v: Vehicle, msg: bytes, rng=None) -> Signature:
    """Eqs. 6-8: commitment, challenge, response; returns Sign_Vi = (r, c) with the ZKP's mu."""
    rng = rng or np.random.default_rng(secrets.randbits(64))
    k, g = S.p.k, S.p.gamma
    z1 = rng.integers(-g, g + 1, size=(k, N), dtype=np.int64)
    z2 = rng.integers(-g, g + 1, size=(k, N), dtype=np.int64)
    z1h, z2h = ntt(z1), ntt(z2)
    mu = intt((matvec(S.Ah, z1h) + z2h) % Q)
    c = h2(S.p.tau, v.b, mu, msg)
    ch = ntt(c)
    r1h = (z1h + ch * v.s1h) % Q
    r2h = (z2h + ch * v.s2h) % Q
    r = intt((r1h + matvec(S.Ainv_h, r2h)) % Q)
    return Signature(r, c, mu)


def zkp_verify(S: System, b: np.ndarray, msg: bytes, sig: Signature) -> bool:
    """Eqs. 14-15: mu' = A r - c b must equal mu, and c' = h2(b || mu || m) must equal c."""
    bh = ntt(b)
    mu2 = intt((matvec(S.Ah, ntt(sig.r)) - ntt(sig.c) * bh) % Q)
    if not np.array_equal(mu2, sig.mu % Q):
        return False
    return np.array_equal(h2(S.p.tau, b, sig.mu, msg), sig.c % Q)


def vpd_leaf(pseudonym: bytes, sig: Signature, eta: bytes, t2: int) -> bytes:
    return h1(pseudonym + _b(sig.r) + eta + t2.to_bytes(8, "big"))


def vpd_root(leaves: list[bytes]) -> bytes:
    """Eq. 9: pair leaves (an empty node pads an odd level), parent = h1(left || right), up to the Root."""
    level = list(leaves)
    while len(level) > 1:
        if len(level) % 2:
            level.append(b"\0" * 32)
        level = [h1(level[i] + level[i + 1]) for i in range(0, len(level), 2)]
    return level[0]


def betas(S: System, members: list, root: bytes) -> np.ndarray:
    """Eq. 10: (beta_1..beta_n) = h2(alpha_1, t_1, mu_1, ..., alpha_n, t_n, mu_n, VP identity); one seed over the
    whole platoon, expanded per vehicle."""
    seed = hashlib.shake_256(b"LETA-beta" + b"".join(a + t.to_bytes(8, "big") + _b(mu) for a, t, mu in members) + root)
    s = seed.digest(32)
    return np.stack([sample_in_ball(s + i.to_bytes(4, "big"), S.p.tau) for i in range(len(members))])


@dataclass
class AggSig:
    r_agg: np.ndarray  # k x n
    c_agg: np.ndarray  # n
    root: bytes  # VP identity
    t5: int


def aggregate(S: System, sigs: list[Signature], members: list, root: bytes, t5: int) -> AggSig:
    """Eqs. 11-12 (PL): c_agg = sum beta_i c_i, r_agg = sum beta_i r_i (mod q)."""
    beh = ntt(betas(S, members, root))
    ch = ntt(np.stack([s.c for s in sigs]))
    rh = ntt(np.stack([s.r for s in sigs]))
    c_agg = intt((beh * ch % Q).sum(axis=0) % Q)
    r_agg = intt((beh[:, None, :] * rh % Q).sum(axis=0) % Q)
    return AggSig(r_agg, c_agg, root, t5)


def agg_verify(S: System, agg: AggSig, members: list, mus: list, bs: list, cs: list, now: int, dt: int) -> bool:
    """TEC (Sec. IV-C2): timestamp T - T5 <= dT, recompute beta (Eq. 10), check Eq. 13."""
    if now - agg.t5 > dt:
        return False
    beh = ntt(betas(S, members, agg.root))
    lhs = matvec(S.Ah, ntt(agg.r_agg))
    muh = ntt(np.stack(mus))
    bh = ntt(np.stack(bs))
    ch = ntt(np.stack(cs))
    rhs = (beh[:, None, :] * ((muh + ch[:, None, :] * bh) % Q) % Q).sum(axis=0) % Q
    return np.array_equal(lhs, rhs)
