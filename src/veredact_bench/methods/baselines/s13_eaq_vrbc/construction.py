"""S13 = manuscript ref [13]: X. Zhang, Z. Cai, K. Chen, G. Ha, C. Jia, "Efficient Auditing and Querying in
Verifiable Redactable Blockchain: A Lightweight VDS Protocol with Integrity Verification", IEEE TrustCom 2025
(Scheme/S13_Zhang2025_EAQ-VRBC/S13_fulltext.md). The manuscript calls it "VRBC".

Implements EAQ-VRBC (Sec. III-B) with a 2048-bit RSA modulus as in the paper:
  * Setup              : N = pq, master (e, d); identity keys sk_i = H3(ID_i)^d, pk_i = H3(ID_i); u in QR_N
  * double-trapdoor CH : ch = (X*Y)^{H2(h_prev||m, Y)} g^r ; Redaction with ephemeral y' = H3(x, m')
  * identity-based tag : S = v^d * prod_i sk_i^{c},  c = H0(s||h_s||v)
  * revocation list    : dynamic RSA accumulator acc(R) = u^{prod H1(x)}, H1 -> odd l-bit numbers
                         (no hash-to-prime; non-coprime factors are peeled into s, Alg. 1)
  * Alg. 1             : NonMemWitCreate  -> (a, B, s)
  * Alg. 2             : non-membership witness aggregation (recursive pairwise, balanced) + NI-SimPoE
                         (Wesolowski proof of exponentiation)
  * Alg. 3             : aggregated verification  C*D == u
  * Query / Audit / Update phases
Deviation: the paper asks for safe primes p = 2p'+1, q = 2q'+1; key generation here uses standard RSA primes
(`cryptography`) for speed. All equations are unchanged. In Alg. 2/3 the base written "u" in the paper is the
accumulator value acc; verification checks acc^{a'} * B'^{x1 x2'} == u.
"""

import hashlib
import math
import secrets
from dataclasses import dataclass, field

from cryptography.hazmat.primitives.asymmetric import rsa

try:  # GMP-backed modular exponentiation (the paper's 2048-bit RSA workload is dominated by it)
    import gmpy2

    def pow(b, e, m=None):  # noqa: A001 — shadow builtin pow within this module
        if m is None:
            return b**e
        if e < 0:
            return int(gmpy2.powmod(gmpy2.invert(b, m), -e, m))
        return int(gmpy2.powmod(b, e, m))
except ImportError:  # pragma: no cover
    pass


def _h(tag: bytes, *parts) -> bytes:
    d = hashlib.sha256(tag)
    for p in parts:
        if isinstance(p, int):
            p = p.to_bytes((p.bit_length() + 8) // 8 or 1, "big", signed=True)
        elif not isinstance(p, bytes):
            p = str(p).encode()
        d.update(p)
        d.update(b"|")
    return d.digest()


def _expand(seed: bytes, nbytes: int) -> int:
    return int.from_bytes(hashlib.shake_256(seed).digest(nbytes), "big")


def is_probable_prime(n: int, rounds: int = 32) -> bool:
    if n < 2:
        return False
    for p in (2, 3, 5, 7, 11, 13, 17, 19, 23, 29):
        if n % p == 0:
            return n == p
    d, s = n - 1, 0
    while d % 2 == 0:
        d, s = d // 2, s + 1
    for _ in range(rounds):
        a = secrets.randbelow(n - 3) + 2
        x = pow(a, d, n)
        if x in (1, n - 1):
            continue
        for _ in range(s - 1):
            x = pow(x, 2, n)
            if x == n - 1:
                break
        else:
            return False
    return True


# ====================================================================== Setup
@dataclass
class Params:
    N: int
    e: int
    d: int
    g: int
    u: int
    l_bits: int
    ids: list
    sk_id: dict  # ID -> H3(ID)^d
    pk_id: dict  # ID -> H3(ID)
    x: int  # CH long-term trapdoor x (SM)
    X: int
    Y: int  # HK = (X, Y)
    y: int

    def H0(self, *p) -> int:
        return _expand(_h(b"H0", *p), self.N.bit_length() // 8) % self.N

    def H1(self, *p) -> int:
        """-> odd numbers in [2^{l-1}, 2^l - 1] (no hash-to-prime)."""
        v = _expand(_h(b"H1", *p), self.l_bits // 8)
        return v | (1 << (self.l_bits - 1)) | 1

    def H2(self, *p) -> int:
        return _expand(_h(b"H2", *p), 32)

    def H3(self, *p) -> int:
        return _expand(_h(b"H3", *p), self.N.bit_length() // 8) % self.N


def setup(rsa_bits=2048, n_miners=4, l_bits=256) -> Params:
    key = rsa.generate_private_key(public_exponent=65537, key_size=rsa_bits)
    nums = key.private_numbers()
    N, e, d = nums.public_numbers.n, nums.public_numbers.e, nums.d
    g = pow(secrets.randbelow(N - 3) + 2, 2, N)  # generator of QR_N (w.h.p.)
    u = pow(secrets.randbelow(N - 3) + 2, 2, N)  # u in QR_N \ {1}
    p = Params(N, e, d, g, u, l_bits, [], {}, {}, 0, 0, 0, 0)
    for i in range(n_miners):
        idb = f"miner-{i}".encode()
        pk = p.H3(idb)
        p.ids.append(idb)
        p.pk_id[idb], p.sk_id[idb] = pk, pow(pk, d, N)
    p.x, p.y = secrets.randbits(256), secrets.randbits(256)
    p.X, p.Y = pow(g, p.x, N), pow(g, p.y, N)
    return p


# ====================================================================== chameleon hash (double trapdoor)
@dataclass
class Block:
    idx: int
    h_prev: bytes
    ch: int
    m: bytes  # MHT root of the block's transactions
    Y: int
    r: int
    ctr: int = 0

    def h(self) -> bytes:
        return _h(b"H3-block", self.ch, self.ctr)


def mht_root(txs: list[bytes]) -> tuple[bytes, int]:
    """Merkle root and #hash ops (2^{l+1} term of Tables II/III)."""
    level, ops = [hashlib.sha256(t).digest() for t in txs], len(txs)
    while len(level) > 1:
        if len(level) % 2:
            level.append(level[-1])
        level = [hashlib.sha256(level[i] + level[i + 1]).digest() for i in range(0, len(level), 2)]
        ops += len(level)
    return level[0], ops


def ch_compute(p: Params, h_prev: bytes, m: bytes, Y: int, r: int) -> int:
    return pow(p.X * Y % p.N, p.H2(h_prev, m, Y), p.N) * pow(p.g, r, p.N) % p.N


def upload_block(p: Params, idx: int, h_prev: bytes, txs: list[bytes]) -> Block:
    m, _ = mht_root(txs)
    r = secrets.randbits(p.N.bit_length())
    return Block(idx, h_prev, ch_compute(p, h_prev, m, p.Y, r), m, p.Y, r)


def redact_block(p: Params, b: Block, txs_new: list[bytes]) -> Block:
    """k = H2(h||m, Y)(x+y) + r;  y' = H3(x, m');  r' = k - H2(h||m', Y')(x + y')  (exact integers)."""
    m_new, _ = mht_root(txs_new)
    y_cur = p.y if b.Y == p.Y else b._y  # current ephemeral trapdoor
    k = p.H2(b.h_prev, b.m, b.Y) * (p.x + y_cur) + b.r
    y_new = p.H3(p.x, m_new)
    Y_new = pow(p.g, y_new, p.N)
    r_new = k - p.H2(b.h_prev, m_new, Y_new) * (p.x + y_new)
    nb = Block(b.idx, b.h_prev, b.ch, m_new, Y_new, r_new, b.ctr)
    nb._y = y_new
    return nb


def ch_verify(p: Params, b: Block) -> bool:
    return b.ch == ch_compute(p, b.h_prev, b.m, b.Y, b.r)


# ====================================================================== identity-based tags
@dataclass
class Tag:
    S: int
    v: int


def tag_gen(p: Params, s: int, h_s: bytes) -> tuple[Tag, int, bytes]:
    v = secrets.randbelow(p.N - 2) + 2
    c = p.H0(s, h_s, v)
    S = pow(v, p.d, p.N)
    for idb in p.ids:
        S = S * pow(p.sk_id[idb], c, p.N) % p.N
    return Tag(S, v), c, p.H3(s, h_s, v)  # hh_s = H3(s||h_s||v)


def tag_verify(p: Params, s: int, h_s: bytes, t: Tag) -> bool:
    """v' = S^e * prod pk_i^{-c};  accept iff v' == v and H0(s||h_s||v') == c."""
    c = p.H0(s, h_s, t.v)
    v2 = pow(t.S, p.e, p.N)
    for idb in p.ids:
        v2 = v2 * pow(p.pk_id[idb], -c, p.N) % p.N
    return v2 == t.v and p.H0(s, h_s, v2) == c


# ====================================================================== RSA accumulator (revocation list)
@dataclass
class Accumulator:
    p: Params
    revoked: list = field(default_factory=list)  # H1 values
    acc: int = 0
    dd: list = field(default_factory=lambda: [1])

    def __post_init__(self):
        self.acc = self.p.u

    def revoke(self, x_h1: int):
        self.revoked.append(x_h1)
        self.acc = pow(self.acc, x_h1, self.p.N)

    def theta(self) -> int:
        return math.prod(self.revoked) * math.prod(self.dd)


def ext_gcd(a: int, b: int):
    if b == 0:
        return a, 1, 0
    x0, x1, y0, y1 = 1, 0, 0, 1
    while b:
        q, a, b = a // b, b, a % b
        x0, x1 = x1, x0 - q * x1
        y0, y1 = y1, y0 - q * y1
    return a, x0, y0


@dataclass
class NonMemWit:  # w_x = (a, B, s)
    a: int
    B: int
    s: list


def nonmem_create(A: Accumulator, x_h1: int) -> NonMemWit:
    """Alg. 1 NonMemWitCreate."""
    theta, x, s = A.theta(), x_h1, [1]
    while (g := math.gcd(theta, x)) != 1:
        x //= g
        s.append(g)
    _, a, b = ext_gcd(theta, x)  # a*theta + b*x = 1
    return NonMemWit(a, pow(A.p.u, b, A.p.N), s)


def nonmem_verify(A: Accumulator, x_h1: int, w: NonMemWit) -> bool:
    """acc^a * B^{x/prod s} == u, with every peeled factor s[i] <= 2^tau."""
    if any(f > 1 << 64 for f in w.s):
        return False
    x = x_h1 // math.prod(w.s)
    return pow(A.acc, w.a, A.p.N) * pow(w.B, x, A.p.N) % A.p.N == A.p.u


# ---- NI-SimPoE (Wesolowski proof of exponentiation) -----------------------------------------------
def _hash_prime(*parts) -> int:
    c = int.from_bytes(_h(b"PoE", *parts)[:16], "big") | 1
    while not is_probable_prime(c):
        c += 2
    return c


def poe_prove(N: int, base: int, exp: int, y: int) -> int:
    ell = _hash_prime(base, exp, y)
    return pow(base, exp // ell, N)


def poe_verify(N: int, base: int, exp: int, y: int, pi: int) -> bool:
    ell = _hash_prime(base, exp, y)
    return pow(pi, ell, N) * pow(base, exp % ell, N) % N == y % N


@dataclass
class AggWit:
    a: int
    B: int
    xs: list  # normalized x_j (after peeling)
    C: int = 0
    D: int = 0
    pi_C: int = 0
    pi_D: int = 0
    peeled: list = field(default_factory=list)  # shared factors removed during aggregation


def _merge(N: int, acc: int, w1: tuple, w2: tuple):
    """Alg. 2 core: merge (a1, B1, X1) and (a2, B2, X2) with gcd(X1, X2) = 1 into (a', B', X1 X2)."""
    a1, B1, X1 = w1
    a2, B2, X2 = w2
    g, al, be = ext_gcd(X1, X2)  # al*X1 + be*X2 = 1
    if g != 1:
        raise ValueError("aggregation inputs must be pairwise coprime (peel first)")
    gamma = a1 * be * X2 + a2 * al * X1
    prod = X1 * X2
    return gamma % prod, pow(acc, gamma // prod, N) * pow(B1, be, N) * pow(B2, al, N) % N, prod


def nonmem_aggregate(A: Accumulator, items: list[tuple[int, NonMemWit]]) -> AggWit:
    """Alg. 2: recursive pairwise aggregation, applied as a balanced tree so merged operands stay similar in
    size (O(c log c) instead of O(c^2) for a left fold). Attaches C = acc^{a'}, D = B'^{X} and two NI-SimPoE."""
    N, acc = A.p.N, A.acc
    # peel factors shared with earlier items (paper: dd = gcd(x1, x2), x2' = x2/dd, s2' = s2 || dd).
    # A witness for X is also one for X/g after B <- B^g, since acc^a (B^g)^{X/g} = acc^a B^X = u.
    level, peeled, P = [], [], 1
    for xh, w in items:
        X, B = xh // math.prod(w.s), w.B
        while (g := math.gcd(P, X)) != 1:
            X //= g
            B = pow(B, g, N)
            peeled.append(g)
        if X > 1:
            level.append((w.a, B, X))
            P *= X
    xs = [w[2] for w in level]
    while len(level) > 1:
        nxt = [_merge(N, acc, level[i], level[i + 1]) for i in range(0, len(level) - 1, 2)]
        if len(level) % 2:
            nxt.append(level[-1])
        level = nxt
    a1, B1, X = level[0]
    C, D = pow(acc, a1, N), pow(B1, X, N)
    return AggWit(a1, B1, xs, C, D, poe_prove(N, acc, a1, C), poe_prove(N, B1, X, D), peeled)


def nonmem_verify_agg(A: Accumulator, w: AggWit) -> bool:
    """Alg. 3: check PoE for C and D, then C * D == u (mod N)."""
    N, X = A.p.N, math.prod(w.xs)
    if any(f > 1 << 64 for f in w.peeled):  # peeled factors must stay below 2^tau
        return False
    return poe_verify(N, A.acc, w.a, w.C, w.pi_C) and poe_verify(N, w.B, X, w.D, w.pi_D) and w.C * w.D % N == A.p.u


# ====================================================================== ledger + Query / Audit / Update
@dataclass
class Ledger:
    p: Params
    blocks: list = field(default_factory=list)
    tags: dict = field(default_factory=dict)  # s -> (Tag, c, hh)
    txs: dict = field(default_factory=dict)
    acc: Accumulator = None

    def __post_init__(self):
        self.acc = Accumulator(self.p)

    def upload(self, txs: list[bytes]) -> Block:
        h_prev = self.blocks[-1].h() if self.blocks else b"genesis"
        b = upload_block(self.p, len(self.blocks), h_prev, txs)
        self.blocks.append(b)
        self.txs[b.idx] = txs
        self.tags[b.idx] = tag_gen(self.p, b.idx, b.h())
        return b

    def redact(self, s: int, txs_new: list[bytes]) -> bool:
        """Redaction + Update (Sec. III-B): the Miner checks the current tag, revokes it in the accumulator; the
        SM computes the collision; the Auditee verifies the CH equation; a new tag is issued and checked by
        the Auditee. False (nothing replaced) if any check fails."""
        t_old, _, hh = self.tags[s]
        if not tag_verify(self.p, s, self.blocks[s].h(), t_old):
            return False
        nb = redact_block(self.p, self.blocks[s], txs_new)
        if not ch_verify(self.p, nb):
            return False
        t_new = tag_gen(self.p, s, nb.h())
        if not tag_verify(self.p, s, nb.h(), t_new[0]):
            return False
        self.acc.revoke(self.p.H1(s, hh))
        self.blocks[s], self.txs[s], self.tags[s] = nb, txs_new, t_new
        return True

    # ---- Query ----
    def query_prove(self, s: int):
        t, c, hh = self.tags[s]
        return self.blocks[s], t, hh, nonmem_create(self.acc, self.p.H1(s, hh))

    def query_verify(self, s: int, proof) -> bool:
        b, t, hh, w = proof
        return nonmem_verify(self.acc, self.p.H1(s, hh), w) and tag_verify(self.p, s, b.h(), t) and ch_verify(self.p, b)

    # ---- Audit ----
    def challenge(self, k: int):
        idx = sorted(secrets.SystemRandom().sample(range(len(self.blocks)), k))
        return [(i, secrets.randbits(64) + 1) for i in idx]

    def audit_prove(self, chal):
        N = self.p.N
        V = S = 1
        mu = 0
        items = []
        for i, beta in chal:
            t, c, hh = self.tags[i]
            V, S, mu = V * pow(t.v, beta, N) % N, S * pow(t.S, beta, N) % N, mu + beta * c
            items.append((self.p.H1(i, hh), nonmem_create(self.acc, self.p.H1(i, hh))))
        return (V, S), mu, nonmem_aggregate(self.acc, items)

    def audit_verify(self, chal, proof) -> bool:
        """(prod S_i^{beta_i})^e == prod v_i^{beta_i} * prod_n H3(ID_n)^{mu}  and the aggregated non-membership."""
        (V, S), mu, w = proof
        p = self.p
        rhs = V
        for idb in p.ids:
            rhs = rhs * pow(p.pk_id[idb], mu, p.N) % p.N
        return pow(S, p.e, p.N) == rhs and nonmem_verify_agg(self.acc, w)
