"""S34 = manuscript ref [34]: J. Xue et al., "Attribute-Based Policy-Hiding Redactable Blockchain With
Authorizable Verification for Energy Internet", IEEE IoT-J 2025 (Scheme/S34_Xue2025_REBS/S34_fulltext.md).

Implements REBS (Sec. V):
  GPGen / KeyTS / KeyTR / KeyAVN        AMC RSA key (n, p, q, alpha), large prime e > max modulus,
                                         TS signing key, TR chameleon-hash key k_TR = (p, q) + Sig_AMC,
                                         AVN authority keys (eps_i, eta_i)
  LSSSConvert                            (t, l) threshold policy -> Vandermonde LSSS matrix (Liu et al.)
  CHash                                  ephemeral RSA (n~, p~, q~); h = H(Tx)^t r^e mod n n~;
                                         Trap = (p~, q~) encrypted under the LSSS policy (attribute VALUES
                                         hidden, names public = partial policy hiding)
  ChVer                                  h == H(Tx)^t r^e mod n n~
  AttrKeyGen                             AVN_i checks Sig_AMC, issues k_attr = g^{eps_i t_i} h_ID^{eta_i}
  ChCld                                  recover Trap with the attribute keys, check h_Trap,
                                         d = e^{-1} mod phi(n n~), r~ = (h H(Tx')^{-t})^d
  TimeUpdate                             r' = r ((H(Tx)^{Dt})^{-1})^d, TS signature
Deviations (docs/baselines/S34-rebs.md): the paper's composite-order group N = p1 p2 p3 is translated to
prime-order BLS12-381 (asymmetric; the standard dual-system -> prime-order translation keeps every
decryption equation); Trap is encapsulated as Trap XOR KDF(e(g,g)^s) because GT is a group, not a
message space. Delegate (AVN join/leave) is not exercised by the VeRedact experiments and not built.
"""

import hashlib
import secrets
from dataclasses import dataclass

import gmpy2
from cryptography.hazmat.primitives.asymmetric import rsa
from py_arkworks_bls12381 import GT, G1Point, G2Point, Scalar

R_ORDER = 0x73EDA753299D7D483339D80809A1D80553BDA402FFFE5BFEFFFFFFFF00000001
G1, G2 = G1Point(), G2Point()
DST = b"VEREDACT-S34-REBS-H2C"


def sc(x: int) -> Scalar:
    return Scalar.from_be_bytes_mod_order((x % R_ORDER).to_bytes(32, "big"))


def rnd() -> int:
    return secrets.randbelow(R_ORDER - 1) + 1


def gt_multiexp(bases: list, exps: list) -> GT:
    """prod bases[i]^exps[i] with one shared squaring chain (Straus); the library has no GT pow."""
    exps = [e % R_ORDER for e in exps]
    out = GT.one()
    for bit in range(max(e.bit_length() for e in exps) - 1, -1, -1):
        out = out * out
        for b, e in zip(bases, exps):
            if (e >> bit) & 1:
                out = out * b
    return out


def kdf(x: GT, n: int) -> bytes:
    return hashlib.shake_256(b"REBS-KDF|" + str(x).encode()).digest(n)


def H_ID(tag: int, identity: bytes) -> G1Point:
    return G1Point.hash_to_curve(DST, bytes([tag]) + identity)


def H_tx(tx: bytes, modulus: int) -> int:
    return int.from_bytes(hashlib.shake_256(b"REBS-H|" + tx).digest(modulus.bit_length() // 8 + 16), "big") % modulus


def rsa_key(bits: int):
    k = rsa.generate_private_key(public_exponent=65537, key_size=bits).private_numbers()
    return k.public_numbers.n, k.p, k.q


# ============================================================================== LSSS (threshold policy)
def lsss_threshold(l: int, t: int) -> list[list[int]]:
    """(t, l) threshold access structure -> l x t Vandermonde LSSS matrix (Liu et al. conversion, Eq. (1))."""
    return [[pow(i, j, R_ORDER) for j in range(t)] for i in range(1, l + 1)]


def lsss_coefficients(rows: list[int], t: int) -> dict[int, int]:
    """mu_i with sum mu_i A_i = (1, 0, ..., 0) for t authorized rows (Lagrange at 0 over x = row+1)."""
    xs = [r + 1 for r in rows[:t]]
    mu = {}
    for r, xi in zip(rows[:t], xs):
        num = den = 1
        for xj in xs:
            if xj != xi:
                num = num * (-xj) % R_ORDER
                den = den * (xi - xj) % R_ORDER
        mu[r] = num * pow(den, -1, R_ORDER) % R_ORDER
    return mu


# ============================================================================== setup
@dataclass
class AMC:
    n: int
    p: int
    q: int
    alpha: int
    g_alpha: G2Point
    e_big: int  # prime e > max RSA modulus


@dataclass
class AVN:
    eps: int
    eta: int
    pk_eta: G2Point  # g^eta


def gpgen(rsa_bits: int) -> AMC:
    n, p, q = rsa_key(rsa_bits)
    alpha = rnd()
    e_big = int(gmpy2.next_prime(1 << (2 * rsa_bits + 1)))  # e > n n~ (both moduli rsa_bits long)
    return AMC(n, p, q, alpha, G2 * sc(alpha), e_big)


def key_avn() -> AVN:
    eps, eta = rnd(), rnd()
    return AVN(eps, eta, G2 * sc(eta))


def key_tr(amc: AMC, identity: bytes):
    """k_TR = (p, q) and Sig_AMC = H_ID(1, ID)^alpha, over a secure channel."""
    return (amc.p, amc.q), H_ID(1, identity) * sc(amc.alpha)


# ============================================================================== policy + CHash
@dataclass
class Policy:
    A: list  # LSSS matrix rows (attribute names = row index -> AVN index, public)
    values: list  # attribute values t_rho(l) (HIDDEN: only inside ciphertext exponents)
    t: int


@dataclass
class Ciphertext:  # Info_Trap
    c0: bytes
    c1: list  # GT
    c2: list  # G2: g^{r_l}
    c3: list  # G2: g^{r_l eta} g^{theta_l}
    h_trap: bytes


@dataclass
class CHValue:
    h: int
    t: int
    r: int
    n_tilde: int
    info: Ciphertext


def chash(amc: AMC, avns: list, policy: Policy, tx: bytes, t: int, rsa_bits: int, eph=None) -> tuple[CHValue, int, int]:
    n_t, p_t, q_t, r, h = chash_rsa(amc.n, amc.e_big, tx, t, rsa_bits, eph)
    return chash_ct(avns, policy, h, t, r, n_t, p_t, q_t, rsa_bits), p_t, q_t


def chash_rsa(amc_n: int, e_big: int, tx: bytes, t: int, rsa_bits: int, eph=None) -> tuple:
    """CHash, integer part: ephemeral RSA trapdoor and h = H(tx)^t * r^e mod N*n~ (plain ints: pools)."""
    n_t, p_t, q_t = eph or rsa_key(rsa_bits)
    M = amc_n * n_t
    r = secrets.randbelow(M - 2) + 2
    h = int(gmpy2.powmod(H_tx(tx, M), t, M)) * int(gmpy2.powmod(r, e_big, M)) % M
    return n_t, p_t, q_t, r, h


def chash_ct(
    avns: list, policy: Policy, h: int, t: int, r: int, n_t: int, p_t: int, q_t: int, rsa_bits: int
) -> CHValue:
    """CHash, pairing part: Trap = (p~, q~) encrypted under the policy (GT values: main process only)."""
    trap = p_t.to_bytes(rsa_bits // 16 + 8, "big") + q_t.to_bytes(rsa_bits // 16 + 8, "big")
    # encrypt Trap under the policy
    m = policy.t
    v = [rnd() for _ in range(m)]
    w = [0] + [rnd() for _ in range(m - 1)]
    lam = [sum(a * b for a, b in zip(row, v)) % R_ORDER for row in policy.A]
    th = [sum(a * b for a, b in zip(row, w)) % R_ORDER for row in policy.A]
    c1, c2, c3 = [], [], []
    for l, _row in enumerate(policy.A):
        a = avns[l]
        rl = rnd()
        c1.append(GT.pairing(G1 * sc(lam[l] + a.eps * policy.values[l] * rl), G2))
        c2.append(G2 * sc(rl))
        c3.append(a.pk_eta * sc(rl) + G2 * sc(th[l]))
    c0 = bytes(x ^ y for x, y in zip(trap, kdf(GT.pairing(G1 * sc(v[0]), G2), len(trap))))
    info = Ciphertext(c0, c1, c2, c3, hashlib.sha3_256(trap).digest())
    return CHValue(h, t, r, n_t, info)


def chver(amc: AMC, tx: bytes, v: CHValue) -> bool:
    M = amc.n * v.n_tilde
    return v.h == int(gmpy2.powmod(H_tx(tx, M), v.t, M)) * int(gmpy2.powmod(v.r, amc.e_big, M)) % M


# ============================================================================== redaction
def attr_keygen(amc: AMC, avn: AVN, identity: bytes, sig_amc: G1Point, value: int) -> G1Point | None:
    """AVN_i: verify e(g, Sig_AMC) = e(H_ID(1, ID), g^alpha), then k = g^{eps_i t_i} h_ID^{eta_i}."""
    if GT.pairing(sig_amc, G2) != GT.pairing(H_ID(1, identity), amc.g_alpha):
        return None
    return G1 * sc(avn.eps * value) + H_ID(0, identity) * sc(avn.eta)


def recover_trap(policy: Policy, info: Ciphertext, identity: bytes, keys: dict[int, G1Point]) -> bytes | None:
    """Trap = c0 XOR KDF(prod_l (c1_l e(h_ID, c3_l) / e(k_l, c2_l))^{mu_l} ), over t rows the TR holds keys for."""
    rows = sorted(keys)
    if len(rows) < policy.t:
        return None
    mu = lsss_coefficients(rows, policy.t)
    hid = H_ID(0, identity)
    use = rows[: policy.t]
    # prod_l c1_l^mu_l * e(h_ID^mu_l, c3_l) * e(k_l^-mu_l, c2_l): exponents moved into G1, one multi-pairing
    g1s = [hid * sc(mu[l]) for l in use] + [-(keys[l] * sc(mu[l])) for l in use]
    acc = gt_multiexp([info.c1[l] for l in use], [mu[l] for l in use]) * GT.multi_pairing(
        g1s, [info.c3[l] for l in use] + [info.c2[l] for l in use]
    )
    trap = bytes(x ^ y for x, y in zip(info.c0, kdf(acc, len(info.c0))))
    return trap if hashlib.sha3_256(trap).digest() == info.h_trap else None


def chcld(amc: AMC, k_tr: tuple, trap: bytes, v: CHValue, tx_new: bytes) -> CHValue:
    half = len(trap) // 2
    p_t, q_t = int.from_bytes(trap[:half], "big"), int.from_bytes(trap[half:], "big")
    p, q = k_tr
    M = amc.n * v.n_tilde
    d = int(gmpy2.invert(amc.e_big, (p - 1) * (q - 1) * (p_t - 1) * (q_t - 1)))
    Ht = int(gmpy2.powmod(H_tx(tx_new, M), v.t, M))
    r_new = int(gmpy2.powmod(v.h * int(gmpy2.invert(Ht, M)) % M, d, M))
    return CHValue(v.h, v.t, r_new, v.n_tilde, v.info)


def time_update(amc: AMC, k_tr: tuple, trap: bytes, v: CHValue, tx: bytes, dt: int) -> CHValue:
    half = len(trap) // 2
    p_t, q_t = int.from_bytes(trap[:half], "big"), int.from_bytes(trap[half:], "big")
    p, q = k_tr
    M = amc.n * v.n_tilde
    d = int(gmpy2.invert(amc.e_big, (p - 1) * (q - 1) * (p_t - 1) * (q_t - 1)))
    inv = int(gmpy2.invert(int(gmpy2.powmod(H_tx(tx, M), dt, M)), M))
    return CHValue(v.h, v.t + dt, v.r * int(gmpy2.powmod(inv, d, M)) % M, v.n_tilde, v.info)
