"""H, H1, H2, H_A (domain-separated SHA3-256) and PRF (HMAC-SHA3-256), as in Phase 1 / Sec. Experimental Setup."""
import hashlib
import hmac

DIGEST_SIZE = 32  # |h| in bytes


def _enc(parts):
    """Unambiguous encoding of a || b || ... (length-prefixed), so H(a||b) != H(a'||b')."""
    out = bytearray()
    for p in parts:
        if isinstance(p, str):
            p = p.encode()
        elif isinstance(p, int):
            p = p.to_bytes(16, "big", signed=True)
        elif p is None:
            p = b""
        out += len(p).to_bytes(4, "big") + p
    return bytes(out)


def _h(domain: bytes, *parts) -> bytes:
    return hashlib.sha3_256(domain + _enc(parts)).digest()


def H(*parts) -> bytes:
    return _h(b"VRPQ/H", *parts)


def H1(*parts) -> bytes:
    return _h(b"VRPQ/H1", *parts)


def H2(*parts) -> bytes:
    return _h(b"VRPQ/H2", *parts)


def HA(*parts) -> bytes:
    return _h(b"VRPQ/HA", *parts)


def PRF(key: bytes, *parts) -> bytes:
    return hmac.new(key, _enc(parts), hashlib.sha3_256).digest()


def to_int(digest: bytes) -> int:
    return int.from_bytes(digest, "big")
