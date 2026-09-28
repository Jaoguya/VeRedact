"""PQCH — SIS-based chameleon hash with an MP12 gadget trapdoor and t-of-n adaptation.

Construction (Cash-Hofheinz-Kiltz-Peikert style chameleon hash, Micciancio-Peikert 2012 trapdoor):

    public key   A = [Abar | G - Abar R]  in Z_q^{n x (mbar + n k)},   q = 2^k,  G = I_n (x) (1,2,...,2^{k-1})
    trapdoor     R in Z^{mbar x n k}, small;  A [R; I] = G
    Hash(m; r)   CH = A r + H_q(m)  (mod q),  r <- D_{Z^M, s}
    Verify       CH == A r + H_q(m)  and  ||r||_2 <= beta
    Collision    r' <- SampleD(A, R, u = A r + H_q(m) - H_q(m'))      so CH(m'; r') = CH(m; r)

    SampleD (MP12 Alg. 3):  p <- perturbation with covariance s^2 I - sigma_g^2 [R;I][R;I]^T
                            z <- SampleG(u - A p)      (bit-by-bit, q = 2^k)
                            r' = p + [R; I] z

Collision resistance: two short r != r' with A r + H(m) = A r' + H(m') give a short SIS solution for A
(with H modelled as a random oracle); the bound beta is what makes a trapdoor necessary.

Distributed mode (VeRedact-PQ Phase 1 Step 5 / Phase 5 Step 3):
    DKeyGen   each C_i samples small R_i and publishes Abar R_i;  A = [Abar | G - sum Abar R_i];  R = sum R_i
              is never assembled. Each C_i Shamir-shares R_i over the prime field F_P (P > max |R z|), so
              t members can compute R z without anyone learning R.
    PartAdapt member k returns delta_k = S_k z (mod P) for the public z of this adaptation
    Combine   R z = sum lambda_k delta_k (mod P, lifted to Z); r' = p + [R z; z]
    Reshare   Shamir resharing of the shares to the next committee (proactive; R unchanged)

DOCUMENTED DEVIATION (see docs/baselines + docs/paper-conformance): in distributed mode nobody knows R,
so the perturbation p is sampled spherical with width s_dist instead of the R-corrected covariance. The
adapted randomness then has covariance s_dist^2 I + sigma_g^2 [R;I][R;I]^T, which is NOT independent of R
and leaks statistical information about R over many adaptations. The centralized mode (single trapdoor
holder) uses the correct MP12 perturbation. Costs are representative of the construction either way;
the security of the threshold variant is not claimed by this implementation.

Parameters (n, k, mbar, sigma_R, sigma_g, s, beta) come from config — they must be vetted with a lattice
estimator before security claims are made (config marks them [CONFIRM]).
"""
import hashlib
from dataclasses import dataclass

import numpy as np

SHAMIR_P = (1 << 31) - 1  # Mersenne prime field for Shamir shares of R: every product below fits int64,
                          # and |R z| << P/2 so R z lifts back to Z exactly


@dataclass(frozen=True)
class SISParams:
    n: int  # rows (SIS dimension)
    k: int  # q = 2^k
    mbar: int  # columns of Abar
    sigma_R: float  # trapdoor entry width
    sigma_g: float  # gadget sampling width
    s: float  # preimage / randomness width (centralized)
    s_dist: float  # perturbation width in distributed mode
    beta: float  # accepted ||r||_2 bound

    @property
    def q(self) -> int:
        return 1 << self.k

    @property
    def M(self) -> int:
        return self.mbar + self.n * self.k


def default_params(n=256, k=16, sigma_R=1.0, sigma_g=3.0) -> SISParams:
    """Standard MP12 sizing: mbar = n k, s >= sqrt(sigma_g^2 (s1(R)^2 + 1)) with s1(R) ~ sigma_R (sqrt(mbar)+sqrt(nk))."""
    mbar = n * k
    s1 = sigma_R * (np.sqrt(mbar) + np.sqrt(n * k))
    s = float(np.ceil(1.2 * sigma_g * np.sqrt(s1 ** 2 + 1)))
    s_dist = s
    M = mbar + n * k
    beta = float(1.1 * max(s, s_dist) * np.sqrt(M) + sigma_g * s1 * np.sqrt(n * k))
    return SISParams(n, k, mbar, sigma_R, sigma_g, s, s_dist, beta)


# ------------------------------------------------------------------ helpers
def _hash_to_zq(msg: bytes, n: int, k: int) -> np.ndarray:
    raw = hashlib.shake_256(b"VRPQ-PQCH-H|" + msg).digest(4 * n)
    return (np.frombuffer(raw, dtype=np.uint32).astype(np.int64)) & ((1 << k) - 1)


def _round_gauss(rng, width, size):
    """Discrete Gaussian approximation: continuous N(0, (width/sqrt(2 pi))^2) + randomized rounding."""
    x = rng.normal(0.0, width / np.sqrt(2 * np.pi), size)
    f = np.floor(x)
    return (f + (rng.random(size) < (x - f))).astype(np.int64)


def _sample_coset(rng, sigma, c):
    """Integers from D_{2Z + c, sigma} (c in {0,1}, vectorised) by rounding in the coset."""
    y = rng.normal(0.0, sigma / np.sqrt(2 * np.pi), c.shape)
    base = 2 * np.floor((y - c) / 2) + c
    up = base + 2
    pick_up = rng.random(c.shape) < ((y - base) / 2)
    return np.where(pick_up, up, base).astype(np.int64)


def sample_g(rng, v: np.ndarray, k: int, sigma_g: float) -> np.ndarray:
    """SampleG for q = 2^k: z in Z^{n k} with (I (x) g^T) z = v (mod q), bit by bit."""
    v = v.copy()
    out = np.empty((v.shape[0], k), dtype=np.int64)
    for i in range(k):
        x = _sample_coset(rng, sigma_g, v & 1)
        out[:, i] = x
        v = (v - x) >> 1  # exact: v - x is even
    return out.reshape(-1)


# ------------------------------------------------------------------ keys
@dataclass
class PublicKey:
    params: SISParams
    Abar: np.ndarray  # n x mbar
    A2: np.ndarray  # n x nk  (= G - Abar R)

    def mul(self, r: np.ndarray) -> np.ndarray:
        p = self.params
        return (self.Abar @ r[: p.mbar] + self.A2 @ r[p.mbar:]) % p.q


@dataclass
class TrapdoorShare:
    index: int  # Shamir x-coordinate (committee position, 1-based)
    S: np.ndarray  # mbar x nk share of R over F_P (int64)


class SISChameleonHash:
    def __init__(self, params: SISParams, seed: int | None = None):
        self.p = params
        self.rng = np.random.default_rng(seed)

    # ---- centralized key generation (single trapdoor holder baselines) --------------------------
    def keygen(self):
        p = self.p
        Abar = self.rng.integers(0, p.q, (p.n, p.mbar), dtype=np.int64)
        R = _round_gauss(self.rng, p.sigma_R * np.sqrt(2 * np.pi), (p.mbar, p.n * p.k))
        G = np.kron(np.eye(p.n, dtype=np.int64), (1 << np.arange(p.k, dtype=np.int64)))
        A2 = (G - Abar @ R) % p.q
        return PublicKey(p, Abar, A2), self._prepare_perturbation(R)

    def _prepare_perturbation(self, R):
        """Genise-Micciancio split: p2 spherical, p1 | p2 with covariance s^2 I - c R R^T (Cholesky once)."""
        p = self.p
        s2, g2 = (p.s / np.sqrt(2 * np.pi)) ** 2, (p.sigma_g / np.sqrt(2 * np.pi)) ** 2
        c = g2 * s2 / (s2 - g2)
        Rf = R.astype(np.float64)
        L = np.linalg.cholesky(s2 * np.eye(p.mbar) - c * (Rf @ Rf.T))
        return {"R": R, "Rf": Rf, "L": L, "coef": -g2 / (s2 - g2), "w2": np.sqrt(s2 - g2)}

    def _perturb_central(self, td):
        p = self.p
        p2 = self.rng.normal(0.0, td["w2"], p.n * p.k)
        mean1 = td["coef"] * (td["Rf"] @ p2)
        p1 = mean1 + td["L"] @ self.rng.normal(0.0, 1.0, p.mbar)
        x = np.concatenate([p1, p2])
        f = np.floor(x)
        return (f + (self.rng.random(x.shape) < (x - f))).astype(np.int64)

    # ---- hashing ---------------------------------------------------------------------------------
    def H(self, msg: bytes) -> np.ndarray:
        return _hash_to_zq(msg, self.p.n, self.p.k)

    def sample_r(self) -> np.ndarray:
        return _round_gauss(self.rng, self.p.s, self.p.M)

    def hash(self, pk: PublicKey, msg: bytes, r: np.ndarray) -> bytes:
        return ((pk.mul(r) + self.H(msg)) % self.p.q).astype(np.uint32).tobytes()

    def verify(self, pk: PublicKey, ch: bytes, msg: bytes, r: np.ndarray) -> bool:
        return float(np.linalg.norm(r)) <= self.p.beta and self.hash(pk, msg, r) == ch

    def _target(self, pk, msg, r, msg_new):
        return (pk.mul(r) + self.H(msg) - self.H(msg_new)) % self.p.q

    # ---- centralized collision (T_AD) ---------------------------------------------------------------
    def adapt(self, pk: PublicKey, td, msg: bytes, r, msg_new: bytes) -> np.ndarray:
        p = self.p
        u = self._target(pk, msg, r, msg_new)
        pert = self._perturb_central(td)
        z = sample_g(self.rng, (u - pk.mul(pert)) % p.q, p.k, p.sigma_g)
        return pert + np.concatenate([td["R"] @ z, z])

    # ---- distributed key generation / resharing -------------------------------------------------------
    def dkeygen(self, n_members: int, t: int):
        """Dealerless: A = [Abar | G - sum_i Abar R_i]; each R_i Shamir-shared t-of-n over F_P."""
        p = self.p
        Abar = self.rng.integers(0, p.q, (p.n, p.mbar), dtype=np.int64)
        G = np.kron(np.eye(p.n, dtype=np.int64), (1 << np.arange(p.k, dtype=np.int64)))
        width = p.sigma_R * np.sqrt(2 * np.pi) / np.sqrt(n_members)  # sum of n contributions has width sigma_R
        A2 = G.copy()
        shares = {k: np.zeros((p.mbar, p.n * p.k), dtype=np.int64) for k in range(1, n_members + 1)}
        for _ in range(n_members):
            R_i = _round_gauss(self.rng, width, (p.mbar, p.n * p.k))
            A2 = (A2 - Abar @ R_i) % p.q  # C_i publishes Abar R_i
            for k, sh in self._shamir(R_i, n_members, t).items():
                shares[k] = (shares[k] + sh) % SHAMIR_P
        return PublicKey(p, Abar, A2), {k: TrapdoorShare(k, v) for k, v in shares.items()}

    def _shamir(self, secret, n_members, t):
        coeffs = [secret % SHAMIR_P] + [self.rng.integers(0, SHAMIR_P, secret.shape, dtype=np.int64)
                                        for _ in range(t - 1)]
        out = {}
        for x in range(1, n_members + 1):
            acc = np.zeros_like(secret)
            for c in reversed(coeffs):
                acc = (_mulmod(acc, x) + c) % SHAMIR_P
            out[x] = acc
        return out

    def reshare(self, old: dict[int, TrapdoorShare], t_old: int, n_new: int, t_new: int):
        ids = sorted(old)[:t_old]
        lam = lagrange_at_zero(ids)
        new = {k: np.zeros_like(old[ids[0]].S) for k in range(1, n_new + 1)}
        for i in ids:
            for k, sh in self._shamir(old[i].S, n_new, t_new).items():
                new[k] = (new[k] + _mulmod(sh, lam[i])) % SHAMIR_P
        return {k: TrapdoorShare(k, v) for k, v in new.items()}

    # ---- distributed adaptation (T_PA / T_CB) -----------------------------------------------------------
    def begin_adapt(self, pk: PublicKey, msg: bytes, r, msg_new: bytes):
        """Combiner: perturbation p (spherical, width s_dist) and public z = SampleG(u - A p)."""
        p = self.p
        u = self._target(pk, msg, r, msg_new)
        pert = _round_gauss(self.rng, p.s_dist, p.M)
        z = sample_g(self.rng, (u - pk.mul(pert)) % p.q, p.k, p.sigma_g)
        return pert, z

    @staticmethod
    def part_adapt(share: TrapdoorShare, z: np.ndarray) -> tuple[int, np.ndarray]:
        """delta_k = S_k z (mod P)."""
        return share.index, _matvec_mod(share.S, z)

    def combine(self, pert: np.ndarray, z: np.ndarray, deltas: list[tuple[int, np.ndarray]]) -> np.ndarray:
        lam = lagrange_at_zero([k for k, _ in deltas])
        acc = np.zeros(self.p.mbar, dtype=np.int64)
        for k, d in deltas:
            acc = (acc + _mulmod(d, lam[k])) % SHAMIR_P
        Rz = np.where(acc > SHAMIR_P // 2, acc - SHAMIR_P, acc)  # lift to Z
        return pert + np.concatenate([Rz, z])


# ------------------------------------------------------------------ modular arithmetic (int64-exact)
def _mulmod(a: np.ndarray, b: int) -> np.ndarray:
    """(a * b) mod P: a < 2^31, b < 2^31  ->  product < 2^62 fits int64."""
    return ((a % SHAMIR_P) * (int(b) % SHAMIR_P)) % SHAMIR_P


def _matvec_mod(S: np.ndarray, z: np.ndarray) -> np.ndarray:
    """S z mod P: |S| < 2^31, |z_j| small, M_cols <= 2^16  ->  |sum| < 2^31 * 2^7 * 2^16 = 2^54."""
    return (S @ z.astype(np.int64)) % SHAMIR_P


def lagrange_at_zero(ids: list[int]) -> dict[int, int]:
    lam = {}
    for i in ids:
        num = den = 1
        for j in ids:
            if j != i:
                num = num * (-j) % SHAMIR_P
                den = den * (i - j) % SHAMIR_P
        lam[i] = num * pow(den, -1, SHAMIR_P) % SHAMIR_P
    return lam
