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
    sigma: bytes = b""
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
    tamper: str = ""  # workload fault injection: "", "sig", "zk", "policy", "stale", "replay", "absent"
    aux: dict = field(default_factory=dict)  # scheme-specific requester-side material


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
