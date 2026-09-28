"""PQCH: post-quantum chameleon hash with t-of-n distributed adaptation (Phase 1 Step 5, Phase 5 Step 3).

The paper instantiates PQCH as an SIS-based chameleon hash following [10], [17] ("[TBD: confirm
construction]"). A real SIS CH needs lattice trapdoor sampling (e.g. MP12 gadget trapdoors).

`LinearThresholdCH` below is a STRUCTURAL STAND-IN with the same interface and a lattice-like cost
profile (matrix-vector products mod q):

    CH(M, r) = A r + g(M)  (mod q),   trapdoor T = A^{-1}  =>  r' = r + T (g(M) - g(M'))

T is Shamir-shared element-wise over GF(q), so PartAdapt / Combine / Reshare have the exact t-of-n
algebra VeRedact-PQ needs. It is NOT collision resistant (A is public and invertible, so anyone can
compute T). Swap in the SIS construction behind the same methods for security-relevant runs.
"""
import hashlib
from dataclasses import dataclass

import numpy as np

Q = 12289  # prime modulus (NTT-friendly, keeps int64 products safe for dim <= 1024)


def _expand(seed: bytes, n: int, label: bytes) -> np.ndarray:
    """Deterministically expand bytes into n elements of Z_q (SHAKE-256)."""
    raw = hashlib.shake_256(label + seed).digest(4 * n)
    return (np.frombuffer(raw, dtype=np.uint32).astype(np.int64)) % Q


def _inv_mod_matrix(a: np.ndarray) -> np.ndarray:
    """Gauss-Jordan inverse over GF(Q)."""
    n = a.shape[0]
    m = np.concatenate([a % Q, np.eye(n, dtype=np.int64)], axis=1)
    for col in range(n):
        piv = next(r for r in range(col, n) if m[r, col] % Q)
        m[[col, piv]] = m[[piv, col]]
        m[col] = (m[col] * pow(int(m[col, col]), -1, Q)) % Q
        factors = m[:, col].copy()
        factors[col] = 0
        m = (m - np.outer(factors, m[col])) % Q
    return m[:, n:]


def _lagrange_at_zero(xs):
    lam = {}
    for i in xs:
        num, den = 1, 1
        for j in xs:
            if j != i:
                num = num * (-j) % Q
                den = den * (i - j) % Q
        lam[i] = num * pow(den, -1, Q) % Q
    return lam


def _shamir_share(secret: np.ndarray, n: int, t: int, rng) -> dict[int, np.ndarray]:
    coeffs = [secret] + [rng.integers(0, Q, size=secret.shape, dtype=np.int64) for _ in range(t - 1)]
    shares = {}
    for x in range(1, n + 1):
        acc = np.zeros_like(secret)
        for c in reversed(coeffs):  # Horner
            acc = (acc * x + c) % Q
        shares[x] = acc
    return shares


@dataclass
class CHPublicKey:
    seed: bytes
    A: np.ndarray
    dim: int


@dataclass
class TrapdoorShare:
    index: int  # Shamir x-coordinate = committee position k
    T_k: np.ndarray


class LinearThresholdCH:
    name = "LinearThresholdCH (structural stand-in, insecure)"

    def __init__(self, dim=256, seed=b"vrpq-pqch", rng_seed=0):
        self.dim = dim
        self.rng = np.random.default_rng(rng_seed)
        self._seed = seed

    # --- key generation -------------------------------------------------
    def dkeygen(self, n: int, t: int):
        """(pk_CH, {td_k}) <- PQCH.DKeyGen(PP, C_e0, t). Dealer-free DKG is emulated by one sharing."""
        while True:
            A = _expand(self._seed + self.rng.bytes(8), self.dim * self.dim, b"A").reshape(self.dim, self.dim)
            try:
                T = _inv_mod_matrix(A)
                break
            except StopIteration:  # singular, resample
                continue
        shares = _shamir_share(T, n, t, self.rng)
        pk = CHPublicKey(self._seed, A, self.dim)
        return pk, {k: TrapdoorShare(k, s) for k, s in shares.items()}, T

    def reshare(self, old: dict[int, TrapdoorShare], t_old: int, n_new: int, t_new: int):
        """{td_{e,k}} <- PQCH.Reshare({td_{e-1,k}}, C_e, t): proactive resharing, secret unchanged."""
        xs = sorted(old)[:t_old]
        lam = _lagrange_at_zero(xs)
        new = {k: np.zeros((self.dim, self.dim), dtype=np.int64) for k in range(1, n_new + 1)}
        for i in xs:
            sub = _shamir_share(old[i].T_k, n_new, t_new, self.rng)
            for k in new:
                new[k] = (new[k] + lam[i] * sub[k]) % Q
        return {k: TrapdoorShare(k, v) for k, v in new.items()}

    # --- hashing ----------------------------------------------------------
    def g(self, msg: bytes) -> np.ndarray:
        return _expand(msg, self.dim, b"g")

    def sample_r(self) -> np.ndarray:
        return self.rng.integers(0, Q, size=self.dim, dtype=np.int64)

    def hash(self, pk: CHPublicKey, msg: bytes, r: np.ndarray) -> bytes:
        return ((pk.A @ r + self.g(msg)) % Q).astype(np.uint16).tobytes()

    def verify(self, pk, ch: bytes, msg: bytes, r: np.ndarray) -> bool:
        return self.hash(pk, msg, r) == ch

    # --- adaptation -------------------------------------------------------
    def part_adapt(self, td: TrapdoorShare, msg: bytes, r, msg_new: bytes, ctx: bytes = b"") -> tuple[int, np.ndarray]:
        """delta_{b,k} <- PQCH.PartAdapt(td_{e,k}, MR_b, r_b, MR_b', BID_e)."""
        return td.index, (td.T_k @ ((self.g(msg) - self.g(msg_new)) % Q)) % Q

    def combine(self, shares: list[tuple[int, np.ndarray]], r: np.ndarray) -> np.ndarray:
        """r_b' <- PQCH.Combine({delta_{b,k}}), |T_b| >= t."""
        lam = _lagrange_at_zero([k for k, _ in shares])
        acc = np.zeros(self.dim, dtype=np.int64)
        for k, d in shares:
            acc = (acc + lam[k] * d) % Q
        return (r + acc) % Q

    def adapt(self, T: np.ndarray, msg: bytes, r, msg_new: bytes) -> np.ndarray:
        """Centralized adaptation T_AD (single trapdoor holder baselines)."""
        return (r + T @ ((self.g(msg) - self.g(msg_new)) % Q)) % Q

    @property
    def digest_size(self) -> int:
        return 2 * self.dim
