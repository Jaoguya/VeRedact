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
import dataclasses
import hashlib
import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path

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


_DKG_STREAM = 0x444B47  # "DKG": DKG draws from its own stream, so a cache hit never shifts self.rng
_DKG_CACHE_VERSION = "dkg-v1"  # bump when dkeygen's output for a given seed changes
_dkg_memo: dict = {}  # in-process: the most recent committee key only (shares are 134 MB each at n = 256)


class SISChameleonHash:
    def __init__(self, params: SISParams, seed: int | None = None, cache_dir: Path | None = None):
        self.p = params
        self.seed = seed
        self.rng = np.random.default_rng(seed)
        self.cache_dir = cache_dir

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
        """Dealerless DKG, run once per committee (seed, n, t, params) and cached: a committee runs DKG once
        per epoch, and setup is never timed. Draws come from a stream derived from (seed, n, t), so cached
        and uncached runs are identical and the adaptation randomness (self.rng) is unaffected."""
        if self.seed is None:
            return self._dkeygen(self.rng, n_members, t)
        key = hashlib.sha256(json.dumps([_DKG_CACHE_VERSION, self.seed, n_members, t,
                                         dataclasses.astuple(self.p)]).encode()).hexdigest()[:24]
        if key in _dkg_memo:
            return _dkg_memo[key]
        d = self.cache_dir / key if self.cache_dir else None
        if d is not None and (d / "done").exists():
            pk = PublicKey(self.p, np.load(d / "Abar.npy"), np.load(d / "A2.npy"))
            shares = {x: TrapdoorShare(x, np.load(d / f"S{x}.npy")) for x in range(1, n_members + 1)}
        else:
            pk, shares = self._dkeygen(np.random.default_rng([self.seed, _DKG_STREAM, n_members, t]), n_members, t)
            if d is not None:
                tmp = d.with_name(d.name + f".tmp{os.getpid()}")
                tmp.mkdir(parents=True, exist_ok=True)
                np.save(tmp / "Abar.npy", pk.Abar)
                np.save(tmp / "A2.npy", pk.A2)
                for x, sh in shares.items():
                    np.save(tmp / f"S{x}.npy", sh.S)
                (tmp / "done").write_text(json.dumps({"seed": self.seed, "n": n_members, "t": t}))
                shutil.rmtree(d, ignore_errors=True)
                tmp.rename(d)
        for a in (pk.Abar, pk.A2, *(sh.S for sh in shares.values())):
            a.flags.writeable = False  # shared across setups in this process: must never be mutated
        _dkg_memo.clear()
        _dkg_memo[key] = (pk, shares)
        return pk, shares

    def _dkeygen(self, rng, n_members: int, t: int):
        """Dealerless: A = [Abar | G - sum_i Abar R_i]; each R_i Shamir-shared t-of-n over F_P."""
        p = self.p
        shape = (p.mbar, p.n * p.k)
        Abar = rng.integers(0, p.q, (p.n, p.mbar), dtype=np.int64)
        G = np.kron(np.eye(p.n, dtype=np.int64), (1 << np.arange(p.k, dtype=np.int64)))
        width = p.sigma_R * np.sqrt(2 * np.pi) / np.sqrt(n_members)  # sum of n contributions has width sigma_R
        A2 = G.copy()
        Abar_f = Abar.astype(np.float64)
        # Shamir is linear: sum_i Share_i(x) = Poly(sum_i coeffs_i)(x). Summing the members' coefficients and
        # evaluating once per x gives the same shares with n*t instead of n^2*t full-matrix operations.
        coef = [np.zeros(shape, dtype=np.int64) for _ in range(t)]
        for _ in range(n_members):
            R_i = _round_gauss(rng, width, shape)
            A2 = (A2 - _exact_matmul(Abar, Abar_f, R_i, p.q)) % p.q  # C_i publishes Abar R_i
            np.add(coef[0], R_i % SHAMIR_P, out=coef[0])
            np.remainder(coef[0], SHAMIR_P, out=coef[0])
            for j in range(1, t):  # C_i's random Shamir coefficients (same draws, same order as per-member sharing)
                np.add(coef[j], rng.integers(0, SHAMIR_P, shape, dtype=np.int64), out=coef[j])
                np.remainder(coef[j], SHAMIR_P, out=coef[j])
        shares = {x: TrapdoorShare(x, _horner_mod(coef, x)) for x in range(1, n_members + 1)}
        return PublicKey(p, Abar, A2), shares

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


def _exact_matmul(A: np.ndarray, A_f: np.ndarray, R: np.ndarray, q: int) -> np.ndarray:
    """A R over Z via float64 BLAS when every partial sum is an integer below 2^53 (then exact); else int64."""
    if A.shape[1] * (q - 1) * int(np.abs(R).max()) < (1 << 53):
        return np.rint(A_f @ R.astype(np.float64)).astype(np.int64)
    return A @ R


def _horner_mod(coef: list, x: int) -> np.ndarray:
    """sum_j coef[j] x^j mod P for a small x: acc < P and x < 2^7, so acc*x + c < 2^39 fits int64."""
    acc = np.zeros_like(coef[0])
    for c in reversed(coef):
        np.multiply(acc, x, out=acc)
        np.add(acc, c, out=acc)
        np.remainder(acc, SHAMIR_P, out=acc)
    return acc


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
