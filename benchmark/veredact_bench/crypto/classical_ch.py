"""Classical chameleon hash for the baselines' original instantiations (Exp. 4 reference runs).

Implements the discrete-log trapdoor commitment used by ETCH (Liu et al. [27], Sec. III-A / V-C):
    Hash:  e = H(m, r),  h = r * y^e * g^w  mod p
    Adapt: k' random, r' = h / g^k', e' = H(m', r'), w' = k' - e' x  mod q
with t-of-n Adapt via Lagrange-weighted shares of x.

Group: RFC 3526 2048-bit MODP (safe prime p = 2q + 1), g = 4 (generates the order-q subgroup).
"""
import secrets

from .hashing import H, to_int

P = int(
    "FFFFFFFFFFFFFFFFC90FDAA22168C234C4C6628B80DC1CD129024E088A67CC74020BBEA63B139B22514A08798E3404DD"
    "EF9519B3CD3A431B302B0A6DF25F14374FE1356D6D51C245E485B576625E7EC6F44C42E9A637ED6B0BFF5CB6F406B7ED"
    "EE386BFB5A899FA5AE9F24117C4B1FE649286651ECE45B3DC2007CB8A163BF0598DA48361C55D39A69163FA8FD24CF5F"
    "83655D23DCA3AD961C62F356208552BB9ED529077096966D670C354E4ABC9804F1746C08CA18217C32905E462E36CE3B"
    "E39E772C180E86039B2783A2EC07A28FB5C55DF06F4C52C9DE2BCBF6955817183995497CEA956AE515D2261898FA0510"
    "15728E5A8AACAA68FFFFFFFFFFFFFFFF",
    16,
)
Q = (P - 1) // 2
G = 4


class ETCHClassicalCH:
    name = "ETCH DL chameleon hash (2048-bit MODP)"

    def keygen(self):
        x = secrets.randbelow(Q - 1) + 1
        return pow(G, x, P), x

    def _e(self, m: bytes, r: int) -> int:
        return to_int(H("ETCH.e", m, r.to_bytes(256, "big"))) % Q

    def hash(self, y: int, m: bytes):
        r = secrets.randbelow(P - 2) + 2
        w = secrets.randbelow(Q)
        h = r * pow(y, self._e(m, r), P) * pow(G, w, P) % P
        return h, (r, w)

    def verify(self, y: int, h: int, m: bytes, rw) -> bool:
        r, w = rw
        return h == r * pow(y, self._e(m, r), P) * pow(G, w, P) % P

    def adapt(self, x: int, h: int, m_new: bytes):
        k = secrets.randbelow(Q - 1) + 1
        r = h * pow(pow(G, k, P), -1, P) % P
        return r, (k - self._e(m_new, r) * x) % Q

    # --- t-of-n (Lagrange-weighted shares of x; CA aggregation as in ETCH Adapt) ---
    @staticmethod
    def share(x: int, n: int, t: int):
        coeffs = [x] + [secrets.randbelow(Q) for _ in range(t - 1)]
        return {i: sum(c * pow(i, j, Q) for j, c in enumerate(coeffs)) % Q for i in range(1, n + 1)}

    @staticmethod
    def lagrange(xs):
        lam = {}
        for i in xs:
            num = den = 1
            for j in xs:
                if j != i:
                    num = num * (-j) % Q
                    den = den * (i - j) % Q
            lam[i] = num * pow(den, -1, Q) % Q
        return lam

    def threshold_adapt(self, shares: dict[int, int], h: int, m_new: bytes):
        ids = sorted(shares)
        ks = {i: secrets.randbelow(Q - 1) + 1 for i in ids}  # round 1: K_i = g^{k_i}
        K = 1
        for i in ids:
            K = K * pow(G, ks[i], P) % P
        r = h * pow(K, -1, P) % P
        e = self._e(m_new, r)
        lam = self.lagrange(ids)
        w = sum((ks[i] - e * lam[i] * shares[i]) for i in ids) % Q  # round 2: w_i summed by CA
        return r, w
