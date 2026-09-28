"""S27 = manuscript ref [27]: Z. Liu, B. Zhou, Y. Zhao, "Enhancing Redactable Blockchain With Robust and
Efficient Threshold Redaction", IEEE TDSC 2026 (Scheme/S27_Liu2026_ETCH/S27_fulltext.md).

Implements the paper's construction as instantiated in its Sec. VII-B (secp256k1 + SHA-256):
  * ETCH = (Setup, KeyGen, Hash, Verify, Adapt, KeyUpt)                      Sec. V-C
      KeyGen : Pedersen/Feldman DKG, commitments phi_ij = a_ij G             (steps 1-3)
      Hash   : e = H(m, r),  h = r + e*Y + w*G                              (additive form of h = r y^e g^w)
      Adapt  : 2 rounds through the Commitment Aggregator (CA):
               K_i = k_i G -> K = sum K_i -> r' = h - K, e' = H(m', r'),
               w_i = k_i - e' lambda_i s_i -> w' = sum w_i
      KeyUpt : proactive share renewal with zero-constant polynomials       (trapdoor/hash key unchanged)
  * ETCH-based redactable chain (Sec. VI): initiator signs the chameleon hash (ECDSA), Merkle leaf = ETCH,
    redaction replaces (TX, r, w) while the signature stays valid.
"""
import hashlib
import secrets
from dataclasses import dataclass, field

from coincurve import PrivateKey, PublicKey

N = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141  # secp256k1 group order
G = PrivateKey((1).to_bytes(32, "big")).public_key


def mul(P: PublicKey, k: int) -> PublicKey:
    return P.multiply((k % N).to_bytes(32, "big"))


def gmul(k: int) -> PublicKey:
    return mul(G, k)


def add(*Ps: PublicKey) -> PublicKey:
    return PublicKey.combine_keys(list(Ps))


def neg(P: PublicKey) -> PublicKey:
    return mul(P, N - 1)


def rand() -> int:
    return secrets.randbelow(N - 1) + 1


def Hs(*parts) -> int:
    """H: {0,1}* -> {0,1}^tau, interpreted in Z_q (SHA-256 as in the paper)."""
    d = hashlib.sha256()
    for p in parts:
        d.update(p.format() if isinstance(p, PublicKey) else p)
    return int.from_bytes(d.digest(), "big") % N


def lagrange(ids: list[int]) -> dict[int, int]:
    lam = {}
    for i in ids:
        num = den = 1
        for j in ids:
            if j != i:
                num = num * j % N
                den = den * (j - i) % N
        lam[i] = num * pow(den, -1, N) % N
    return lam


# ================================================================== KeyGen (DKG) / KeyUpt
@dataclass
class Participant:
    i: int
    s: int = 0  # trapdoor share s_i
    y: PublicKey | None = None  # hash-key share y_i = s_i G


@dataclass
class ETCHKeys:
    Y: PublicKey  # hash key y = sum phi_j0
    parts: dict[int, Participant]
    t: int
    n: int
    period: int = 0
    _x: int = 0  # joint trapdoor, for tests only (never held by anyone)


def _share_poly(coeffs, x):
    return sum(c * pow(x, k, N) for k, c in enumerate(coeffs)) % N


def _feldman_ok(commit: list[PublicKey], x: int, value: int) -> bool:
    expect = commit[0]
    for k in range(1, len(commit)):
        expect = add(expect, mul(commit[k], pow(x, k, N)))
    return gmul(value) == expect


def keygen(t: int, n: int) -> ETCHKeys:
    polys = {i: [rand() for _ in range(t)] for i in range(1, n + 1)}
    commits = {i: [gmul(a) for a in polys[i]] for i in polys}  # C_i broadcast
    parts = {i: Participant(i) for i in polys}
    for i, p in parts.items():  # P_i verifies every received share, then sums
        for j in polys:
            f_ji = _share_poly(polys[j], i)
            if not _feldman_ok(commits[j], i, f_ji):
                raise ValueError(f"KeyGen: share {j}->{i} rejected")
            p.s = (p.s + f_ji) % N
        p.y = gmul(p.s)
    Y = add(*(commits[j][0] for j in polys))
    return ETCHKeys(Y, parts, t, n, 0, sum(p[0] for p in polys.values()) % N)


def keyupt(keys: ETCHKeys) -> ETCHKeys:
    """Period T: every P_i shares a random delta_i with delta_i(0) = 0; s_i^(T) = s_i^(T-1) + sum_j delta_j(i)."""
    t, ids = keys.t, list(keys.parts)
    deltas = {i: [0] + [rand() for _ in range(t - 1)] for i in ids}
    commits = {i: [gmul(d) for d in deltas[i][1:]] for i in ids}  # g^{delta_i1..}
    for i, p in keys.parts.items():
        for j in ids:
            z = _share_poly(deltas[j], i)
            expect = mul(commits[j][0], i)
            for k in range(2, t):
                expect = add(expect, mul(commits[j][k - 1], pow(i, k, N)))
            if gmul(z) != expect:
                raise ValueError(f"KeyUpt: share {j}->{i} rejected")
            p.s = (p.s + z) % N
        p.y = gmul(p.s)
    keys.period += 1
    return keys


# ================================================================== Hash / Verify / Adapt
@dataclass
class ETCHValue:
    h: PublicKey
    r: PublicKey
    w: int


def hash_(Y: PublicKey, m: bytes) -> ETCHValue:
    r = gmul(rand())  # r in the group
    w = rand()
    e = Hs(m, r)
    return ETCHValue(add(r, mul(Y, e), gmul(w)), r, w)


def verify(Y: PublicKey, m: bytes, v: ETCHValue) -> bool:
    return v.h == add(v.r, mul(Y, Hs(m, v.r)), gmul(v.w))


def adapt(keys: ETCHKeys, signers: list[int], v: ETCHValue, m_new: bytes) -> ETCHValue:
    """Two-round Adapt via the Commitment Aggregator; requires |signers| >= t."""
    if len(signers) < keys.t:
        raise ValueError("fewer than t redactors")
    k = {i: rand() for i in signers}
    K = add(*(gmul(k[i]) for i in signers))  # round 1: K_i -> CA -> K
    r_new = add(v.h, neg(K))  # r' = h / K
    e_new = Hs(m_new, r_new)
    lam = lagrange(signers)
    w_new = sum((k[i] - e_new * lam[i] * keys.parts[i].s) for i in signers) % N  # round 2: w_i -> CA
    return ETCHValue(v.h, r_new, w_new)


# ================================================================== ETCH-based chain (Sec. VI)
@dataclass
class Tx:
    body: bytes
    etch: ETCHValue
    sig: bytes  # initiator's signature on the chameleon hash h


@dataclass
class Block:
    txs: list = field(default_factory=list)



class Initiator:
    def __init__(self):
        self.sk = PrivateKey()

    def create_tx(self, Y: PublicKey, body: bytes) -> Tx:
        v = hash_(Y, body)
        return Tx(body, v, self.sk.sign(v.h.format()))


def verify_tx(Y: PublicKey, pk: PublicKey, tx: Tx) -> bool:
    return verify(Y, tx.body, tx.etch) and pk.verify(tx.sig, tx.etch.h.format())


def redact_tx(keys: ETCHKeys, signers: list[int], tx: Tx, body_new: bytes) -> Tx:
    return Tx(body_new, adapt(keys, signers, tx.etch, body_new), tx.sig)  # signature unchanged


# ================================================================== sizes (Table V)
SIZES = {"sk": 32, "h": 33, "randomness": 33 + 32}  # |Z_q|, point, (point r, scalar w)
