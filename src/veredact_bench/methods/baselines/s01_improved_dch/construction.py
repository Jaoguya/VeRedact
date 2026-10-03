"""S1 = manuscript ref [1]: C. Li, Q. Shen, Z. Wu, "Redactable Blockchain From Decentralized Chameleon
Hash Functions, Revisited", IEEE TC 2025 (Scheme/S1_Li2025_ImprovedDCH/S1_fulltext.md).

Implements, in the paper's classical setting:
  * JiaDCH       — Jia et al.'s decentralized chameleon hash (reviewed in Sec. III-C1)
  * forge_jia    — the paper's collision attack on JiaDCH (Sec. IV-A, Eqs. (1)-(5))
  * BLSChameleon — the proposed base chameleon hash (Sec. V-A)
  * ImprovedDCH  — the proposed t-party DCH (Sec. V-B): DKG + threshold Collision
  * redaction-request / approval flow of Jia's chain (Sec. III-C3) used by the threshold redaction

Pairing: the paper uses a symmetric pairing e: G x G -> GT (PBC Type A/E/F). This implementation uses the
asymmetric BLS12-381 pairing (arkworks) with the standard Type-3 translation: hash values and
randomness live in G1, public keys are published in both G1 and G2 so every equation keeps its form.
    Improved DCH Verify:  e(h - H(m), X2) == e(r, g2)        (paper: e(h/H(m), y) = e(g, r))
    Jia DH-tuple check:   e(g1^e, S2)    == e(g1^{se}, g2)   (paper: (g, g^s, g^e, g^se) is a DH tuple)
"""
import hashlib
import secrets
from dataclasses import dataclass

from py_arkworks_bls12381 import G1Point, G2Point, GT, Scalar

# BLS12-381 scalar field order
R = 0x73EDA753299D7D483339D80809A1D80553BDA402FFFE5BFEFFFFFFFF00000001
G1, G2 = G1Point(), G2Point()
DST = b"VEREDACT-S1-H2C-BLS12381G1"


def sc(x: int) -> Scalar:
    return Scalar.from_be_bytes_mod_order((x % R).to_bytes(32, "big"))


def rand_scalar() -> int:
    return secrets.randbelow(R - 1) + 1


def H_G1(*parts: bytes) -> G1Point:
    """H: {0,1}* -> G (hash-to-curve)."""
    return G1Point.hash_to_curve(DST, b"|".join(parts))


def H_int(*parts: bytes) -> int:
    """ID(.) / message-to-exponent map: {0,1}* -> Z_p*."""
    return int.from_bytes(hashlib.sha256(b"|".join(parts)).digest(), "big") % R or 1


def lagrange_at_zero(ids: list[int]) -> dict[int, int]:
    """lambda_i = prod_{j != i} ID(P_j) / (ID(P_j) - ID(P_i))  mod p."""
    lam = {}
    for i in ids:
        num = den = 1
        for j in ids:
            if j != i:
                num = num * j % R
                den = den * (j - i) % R
        lam[i] = num * pow(den, -1, R) % R
    return lam


# ============================================================ DKG (Sec. III-C1 / V-B KeyGen)
@dataclass
class DKGResult:
    x: int  # joint secret (only for tests; never materialized in the protocol)
    X1: G1Point  # g1^x
    X2: G2Point  # g2^x
    shares: dict[int, int]  # ID(P_i) -> x_i = f(ID(P_i))


def dkg(t: int, n: int | None = None) -> DKGResult:
    """Each P_i picks f_i of degree t-1, sends f_i(ID(P_j)) + commitments, verifies, and sums.

    Commitment check per received share: g^{f_j(ID(P_i))} == prod_k (g^{a_jk})^{ID(P_i)^k}.
    The paper's KeyGen is written for the t participants themselves (n = t); n > t is supported.
    """
    n = n or t
    ids = [H_int(b"P%d" % i) for i in range(1, n + 1)]
    polys = {i: [rand_scalar() for _ in range(t)] for i in ids}
    commits = {i: [G2 * sc(a) for a in polys[i]] for i in ids}  # g^{a_ik}
    shares = {}
    for i in ids:  # P_i collects f_j(ID(P_i)) from every P_j and verifies it
        s_i = 0
        for j in ids:
            f_ji = sum(a * pow(i, k, R) for k, a in enumerate(polys[j])) % R
            expect = commits[j][0]
            for k in range(1, t):
                expect = expect + commits[j][k] * sc(pow(i, k, R))
            if G2 * sc(f_ji) != expect:
                raise ValueError(f"share from {j} to {i} fails its commitment check")
            s_i = (s_i + f_ji) % R
        shares[i] = s_i
    x = sum(p[0] for p in polys.values()) % R
    return DKGResult(x, G1 * sc(x), G2 * sc(x), shares)


# ============================================================ Jia et al. DCH (Sec. III-C1)
@dataclass
class JiaHash:
    h: G1Point
    r: tuple[G1Point, G1Point]  # (g^e, g^{se})


class JiaDCH:
    def __init__(self, key: DKGResult):
        self.k = key  # pk = g^s  (S1 = X1, S2 = X2)

    def label(self, m: bytes) -> G1Point:
        """u = H(g^s, m)."""
        return H_G1(self.k.X1.to_compressed_bytes(), m)

    def hash(self, m: bytes) -> JiaHash:
        u, mi, e = self.label(m), H_int(m), rand_scalar()
        return JiaHash(G1 * sc(e) + u * sc(mi), (G1 * sc(e), self.k.X1 * sc(e)))

    def verify(self, m: bytes, r, m2: bytes, r2) -> bool:
        """Same hash value AND (g, g^s, g^e', g^se') is a Diffie-Hellman tuple."""
        u = self.label(m)
        same = r[0] + u * sc(H_int(m)) == r2[0] + u * sc(H_int(m2))
        dh = GT.pairing(r2[0], self.k.X2) == GT.pairing(r2[1], G2)
        return same and dh

    def collision(self, m: bytes, r, m2: bytes, participants: list[int]):
        """t parties: g^e' = g^e u^{m-m'};  eta_i = (g^e')^{lambda_i s_i};  g^se' = prod eta_i."""
        u = self.label(m)
        ge2 = r[0] + u * sc(H_int(m) - H_int(m2))
        lam = lagrange_at_zero(participants)
        gse2 = G1Point.identity()
        for i in participants:
            gse2 = gse2 + ge2 * sc(lam[i] * self.k.shares[i])
        return ge2, gse2


def forge_jia(dch: JiaDCH, m: bytes, r, m2: bytes, r2, m3: bytes):
    """Sec. IV-A: from ONE published collision (m,r),(m',r') anyone derives r'' for any m'' — no trapdoor.

    (2),(3): u^s = (g^{se'} / g^{se})^{1/(m - m')}
    (4):     g^{e''}  = g^e u^{m - m''}
    (5):     g^{se''} = g^{se} (u^s)^{m - m''}
    """
    u = dch.label(m)
    mi, m2i, m3i = H_int(m), H_int(m2), H_int(m3)
    us = (r2[1] - r[1]) * sc(pow((mi - m2i) % R, -1, R))
    return r[0] + u * sc(mi - m3i), r[1] + us * sc(mi - m3i)


# ============================================================ Base chameleon hash (Sec. V-A)
@dataclass
class BLSHash:
    h: G1Point
    r: G1Point


class BLSChameleon:
    """h = H(m) g^xi,  r = y^xi;  Verify e(h/H(m), y) = e(g, r);  Collision r' = r (H(m)/H(m'))^x."""

    def __init__(self, x: int | None = None):
        self.x = x or rand_scalar()
        self.X1, self.X2 = G1 * sc(self.x), G2 * sc(self.x)

    def hash(self, m: bytes) -> BLSHash:
        xi = rand_scalar()
        return BLSHash(H_G1(m) + G1 * sc(xi), self.X1 * sc(xi))

    def verify(self, m: bytes, r: G1Point, h: G1Point) -> bool:
        return GT.pairing(h - H_G1(m), self.X2) == GT.pairing(r, G2)

    def collision(self, m: bytes, m2: bytes, r: G1Point, h: G1Point) -> G1Point:
        if not self.verify(m, r, h):
            raise ValueError("invalid (m, r, h)")
        return r + (H_G1(m) - H_G1(m2)) * sc(self.x)


# ============================================================ Improved DCH (Sec. V-B)
class ImprovedDCH:
    def __init__(self, key: DKGResult):
        self.k = key
        self.base = BLSChameleon.__new__(BLSChameleon)
        self.base.X1, self.base.X2 = key.X1, key.X2

    def hash(self, m: bytes) -> BLSHash:
        return self.base.hash(m)

    def verify(self, m: bytes, r: G1Point, h: G1Point) -> bool:
        return self.base.verify(m, r, h)

    def partial(self, i: int, lam_i: int, m: bytes, m2: bytes) -> G1Point:
        """eta_i = (H(m)/H(m'))^{lambda_i x_i}."""
        return (H_G1(m) - H_G1(m2)) * sc(lam_i * self.k.shares[i])

    def collision(self, m: bytes, m2: bytes, r: G1Point, h: G1Point, participants: list[int]) -> G1Point:
        """r' = r * prod_j eta_j over t participants."""
        if not self.verify(m, r, h):
            raise ValueError("invalid (m, r, h)")
        lam = lagrange_at_zero(participants)
        out = r
        for i in participants:
            out = out + self.partial(i, lam[i], m, m2)
        return out


def try_forge_improved(dch: ImprovedDCH, m: bytes, r, m2: bytes, r2, h, m3: bytes) -> bool:
    """Apply the same algebraic trick to Improved DCH: r2 - r reveals (H(m)-H(m'))^x, which does not
    yield (H(m)-H(m''))^x for a fresh m'' without the trapdoor (CDH / BLS EU-CMA). Returns True if the
    naive forgery verifies (it must not)."""
    delta = r2 - r  # (H(m) - H(m'))^x
    guess = r + delta  # best trapdoor-free guess reuses the known delta
    return dch.verify(m3, guess, h)


# ============================================================ sizes (Table I)
G1_BYTES = 48  # compressed BLS12-381 G1 point
SIZES = {
    "DCH [Jia]": {"pk": "|G|", "sk": "|Zp|", "h": "|G|", "r": "2|G|", "r_bytes": 2 * G1_BYTES},
    "Improved DCH": {"pk": "|G|", "sk": "|Zp|", "h": "|G|", "r": "|G|", "r_bytes": G1_BYTES},
}
