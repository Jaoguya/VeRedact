"""Protocol objects (names follow the paper's notation table)."""

from dataclasses import dataclass, field

import numpy as np


@dataclass
class Tx:
    TID: bytes
    m: bytes
    rho: bytes
    DT: str
    PID: str
    ts: int
    owner: int
    sigma: bytes = b""  # data-owner ML-DSA signature over H(TID || D_i || DT || PID || ts)
    C_orig: bytes = b""  # provenance commitment H(TID || D_i || sigma_i)
    I: bytes = b""
    D: bytes = b""
    Tag: bytes = b""
    b: int = -1
    pos: int = -1
    e_i: int = 0


@dataclass
class Checkpoint:  # A_b
    b: int
    CH: bytes
    MR: bytes
    r: np.ndarray
    R_RLI: bytes
    v_RLI: int
    e: int
    v_b: int
    ts: int
    sigma: bytes
    # sigma_b signs H(r_b) rather than r_b itself, computed once here. r_b is M = 2nk int64 values
    # (64 KiB), so re-hashing it inside every checkpoint verification cost ~0.25 ms per node; the
    # PQCH equation is what binds r_b to CH_b and MR_b, the signature only has to bind the same value.
    r_digest: bytes = b""
    # h_b^snap = H(enc(State_b)): the snapshot half of h_i^st, so a request can be checked against an
    # earlier anchored checkpoint of its batch without recomputing it (FreshLeaf, condition 3)
    snap: bytes = b""


@dataclass
class Request:  # R_i plus requester-side material sent alongside
    ID_r: int
    TID: bytes
    op: str
    D_new: bytes
    e: int
    ts_r: int
    n_r: bytes
    m_new: bytes = b""
    rho_new: bytes = b""
    sigma_R: bytes = b""
    x: bytes = b""
    proof: bytes = b""
    v_b: int = -1  # batch version the requester proved against (public, read from the checkpoint A_b)
    h_st: bytes = b""  # state digest h_i^st the requester proved against (Phase 3 Step 4)
    tamper: str = ""  # workload fault injection: "", "sig", "zk", "policy", "stale", "replay", "absent"
    aux: dict = field(default_factory=dict)  # scheme-specific requester-side material


@dataclass
class Attestation:  # alpha_i under BatchAttest (P2): (w, R_w^V, MP_i^V, sigma_w^V, ts_i^adm)
    w: int = -1  # admission window
    root: bytes = b""  # R_w^V: Merkle root of the window's leaves lambda_i
    path: list = field(default_factory=list)  # MP_i^V: lambda_i under R_w^V
    sigma: bytes = b""  # sigma_w^V: the VPS's one ML-DSA signature for the whole window
    ts_adm: int = 0  # ts_i^adm (ms), bound in lambda_i: the attestation is also the admission receipt rc_i
    index: int = -1  # leaf position in the window

    def enc(self) -> bytes:
        """Canonical bytes of alpha_i (what eta_i = H_V(AUTH-LEAF || RID || C_VR || alpha_i) commits to)."""
        from ..crypto.hashing import H

        return H(self.w, self.root, self.sigma, self.ts_adm, self.index, *self.path)


@dataclass
class ValidatedRequest:  # VR_i
    RID: bytes
    C_VR: bytes
    b: int
    pos: int
    PID: str
    v_b: int
    e_i: int
    e: int
    sigma_R: bytes
    h_proof: bytes
    alpha: bytes
    req: Request = None  # supporting evidence (off-ledger evidence store)
    t_submit: float = 0.0
    receipt: tuple = ()  # (ts_rc, rc_i): VPS admission receipt returned to the requester
    h_st: bytes = b""  # authenticated transaction-state digest h_i^st
    v_RLI: int = 0  # SA-RLI snapshot of the batch checkpoint the request was validated against
    v_snap: int = -1  # v_b of the anchored checkpoint h_i^st was validated against (FreshLeaf)
    att: Attestation = None  # BatchAttest alpha_i; complete (sigma set) once its admission window has closed


@dataclass
class BatchAuth:  # Auth_e^B
    BID: bytes
    C_B: bytes
    R_VR: bytes
    approvals: list  # [(k, sigma_{e,k}^B)]
    e: int
    ts: int
    members: list = field(default_factory=list)  # VR_i in canonical order
    leaves: list = field(default_factory=list)  # eta_i
    proofs: dict = field(default_factory=dict)  # RID -> MP_i^B
    gamma: bytes = b""  # Gamma_e: CORA authorized execution-plan commitment over the (b_i, pos_i)


@dataclass
class RedactionRecord:  # RR_i (+ PBRP kept alongside for Phase 6)
    RID: bytes
    TID: bytes
    BID: bytes
    PID: str
    D_old: bytes
    D_new: bytes
    v_b: int
    v_b_new: int
    h_pbrp: bytes
    ts_red: int
    b: int = -1
    pos: int = -1
    e: int = 0
    pbrp: dict = field(default_factory=dict)
