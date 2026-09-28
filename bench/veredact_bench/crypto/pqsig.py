"""PQSIG (ML-DSA-65, FIPS 204) plus a classical Ed25519 scheme for the 'original classical instantiation' runs (Exp. 4).

Backends, selected by VRPQ_SIG_BACKEND (default: auto):
  pqcrypto  - ML-DSA-65 via the `pqcrypto` wheel (works out of the box)
  oqs       - ML-DSA-65 via liboqs-python (the paper's stated library; needs `brew install liboqs`)
  sim       - HMAC-based stand-in with ML-DSA-65 sizes; NOT secure, for plumbing tests only
"""
import hashlib
import hmac
import os
import secrets
from dataclasses import dataclass


@dataclass
class KeyPair:
    pk: bytes
    sk: bytes


class SignatureScheme:
    name = "abstract"
    sig_size = 0

    def keygen(self) -> KeyPair:
        raise NotImplementedError

    def sign(self, sk: bytes, msg: bytes) -> bytes:
        raise NotImplementedError

    def verify(self, pk: bytes, msg: bytes, sig: bytes) -> bool:
        raise NotImplementedError


class MLDSA65Pqcrypto(SignatureScheme):
    name = "ML-DSA-65 (pqcrypto)"

    def __init__(self):
        from pqcrypto.sign import ml_dsa_65 as m

        self._m = m
        self.sig_size = m.SIGNATURE_SIZE

    def keygen(self):
        pk, sk = self._m.keygen()
        return KeyPair(pk, sk)

    def sign(self, sk, msg):
        return self._m.sign(sk, msg)

    def verify(self, pk, msg, sig):
        try:
            self._m.verify(pk, msg, sig)
            return True
        except Exception:
            return False


class MLDSA65Oqs(SignatureScheme):
    name = "ML-DSA-65 (liboqs)"

    def __init__(self):
        import oqs  # liboqs-python

        self._oqs = oqs
        with oqs.Signature("ML-DSA-65") as s:
            self.sig_size = s.details["length_signature"]

    def keygen(self):
        s = self._oqs.Signature("ML-DSA-65")
        pk = s.generate_keypair()
        return KeyPair(pk, s.export_secret_key())

    def sign(self, sk, msg):
        with self._oqs.Signature("ML-DSA-65", sk) as s:
            return s.sign(msg)

    def verify(self, pk, msg, sig):
        with self._oqs.Signature("ML-DSA-65") as s:
            return s.verify(msg, sig, pk)


class SimulatedSig(SignatureScheme):
    """Structural stand-in (ML-DSA-65 sizes). Verification uses a shared registry, so it is NOT a real signature."""

    name = "SIMULATED (insecure)"
    sig_size = 3309
    _registry: dict = {}

    def keygen(self):
        sk = secrets.token_bytes(32)
        pk = hashlib.sha3_256(b"pk" + sk).digest().ljust(1952, b"\0")
        self._registry[pk] = sk
        return KeyPair(pk, sk)

    def sign(self, sk, msg):
        tag = hmac.new(sk, msg, hashlib.sha3_256).digest()
        return tag.ljust(self.sig_size, b"\0")

    def verify(self, pk, msg, sig):
        sk = self._registry.get(pk)
        return sk is not None and hmac.compare_digest(sig[:32], hmac.new(sk, msg, hashlib.sha3_256).digest())


class Ed25519(SignatureScheme):
    """Classical signature used for the baselines' original instantiations (|sigma^c| = 64 B)."""

    name = "Ed25519"
    sig_size = 64

    def __init__(self):
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import ed25519

        self._ed, self._ser = ed25519, serialization

    def keygen(self):
        sk = self._ed.Ed25519PrivateKey.generate()
        raw = self._ser.Encoding.Raw
        return KeyPair(
            sk.public_key().public_bytes(raw, self._ser.PublicFormat.Raw),
            sk.private_bytes(raw, self._ser.PrivateFormat.Raw, self._ser.NoEncryption()),
        )

    def sign(self, sk, msg):
        return self._ed.Ed25519PrivateKey.from_private_bytes(sk).sign(msg)

    def verify(self, pk, msg, sig):
        try:
            self._ed.Ed25519PublicKey.from_public_bytes(pk).verify(sig, msg)
            return True
        except Exception:
            return False


def load_pqsig(backend: str | None = None) -> SignatureScheme:
    backend = backend or os.environ.get("VRPQ_SIG_BACKEND", "auto")
    order = {"auto": ["oqs", "pqcrypto"], "oqs": ["oqs"], "pqcrypto": ["pqcrypto"], "sim": ["sim"]}[backend]
    for b in order:
        try:
            return {"oqs": MLDSA65Oqs, "pqcrypto": MLDSA65Pqcrypto, "sim": SimulatedSig}[b]()
        except Exception:
            continue
    raise RuntimeError(f"no ML-DSA-65 backend available for '{backend}'; install pqcrypto or liboqs-python, or use sim")
