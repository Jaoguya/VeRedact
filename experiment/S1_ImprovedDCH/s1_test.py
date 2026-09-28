import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scheme_common import add_folder_to_path  # noqa: E402

add_folder_to_path(__file__)
from s1_scheme import (BLSChameleon, ImprovedDCH, JiaDCH, dkg, forge_jia, lagrange_at_zero, R,  # noqa: E402
                       try_forge_improved)


def test_dkg_shares_reconstruct_secret():
    k = dkg(4, n=6)
    ids = list(k.shares)[:4]
    lam = lagrange_at_zero(ids)
    assert sum(lam[i] * k.shares[i] for i in ids) % R == k.x


def test_base_chameleon_collision():
    ch = BLSChameleon()
    h = ch.hash(b"m")
    assert ch.verify(b"m", h.r, h.h)
    r2 = ch.collision(b"m", b"m2", h.r, h.h)
    assert ch.verify(b"m2", r2, h.h) and not ch.verify(b"m3", r2, h.h)


def test_improved_dch_threshold_and_attack_resistance():
    k = dkg(5)
    ids = list(k.shares)
    d = ImprovedDCH(k)
    h = d.hash(b"m")
    r2 = d.collision(b"m", b"m2", h.r, h.h, ids)
    assert d.verify(b"m2", r2, h.h)
    assert not d.verify(b"m2", d.collision(b"m", b"m2", h.r, h.h, ids[:4]), h.h)  # t-1 shares fail
    assert not try_forge_improved(d, b"m", h.r, b"m2", r2, h.h, b"evil")


def test_jia_dch_is_forgeable():
    k = dkg(5)
    ids = list(k.shares)
    j = JiaDCH(k)
    h = j.hash(b"m")
    r2 = j.collision(b"m", h.r, b"m2", ids)
    assert j.verify(b"m", h.r, b"m2", r2)
    assert j.verify(b"m", h.r, b"evil", forge_jia(j, b"m", h.r, b"m2", r2, b"evil"))  # Sec. IV attack
