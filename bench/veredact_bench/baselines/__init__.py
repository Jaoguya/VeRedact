"""Re-implemented baselines (paper, Sec. Evaluation: 'all baselines were reimplemented within the same
framework and instantiated with the same PQ primitives ... each baseline otherwise follows its original
workflow, including per-request authorization and adaptation').

Each spec reproduces one row of Table IV (computation) and Table V (communication/on-chain state).
`grounded` says where the workflow comes from:
  "pdf"      - checked against the paper in Scheme/ (full text available)
  "table-iv" - taken from VeRedact's own Table IV row, marked TODO-VERIFY in the .tex; no PDF here yet
"""
from .generic import BaselineSpec, PerRequestBaseline

SPECS = {
    # ---- Exp. 1 (end-to-end) primary baselines ------------------------------------------------
    "huang2021": BaselineSpec(
        ref=14, label="Huang et al. [14]", classical_sig=True, validate="sig", authorize="none",
        adapt="central", audit=None, onchain="hash", grounded="table-iv",
        note="Scalable & redactable blockchain with update and anonymity (Inf. Sci. 2021). Single trapdoor holder."),
    "wang2024": BaselineSpec(
        ref=17, label="Wang et al. [17]", classical_sig=False, validate="sig", authorize="none",
        adapt="central", audit=None, onchain="hash", grounded="table-iv",
        note="Quantum-resistant redaction with trapdoor updates (Appl. Sci. 2024). Already PQ."),
    "liu2026_etch": BaselineSpec(
        ref=27, label="Liu et al. [27] (ETCH)", classical_sig=True, validate="sig", authorize="threshold_sign",
        adapt="threshold", audit="threshold_sigs", onchain="hash", grounded="pdf",
        note="ETCH: t-of-n Adapt per redaction (CA aggregation), initiator signs the chameleon hash, "
             "Merkle leaf hash = ETCH. See Scheme/2_ETCH_Liu2026."),
    "xue2026_mainaux": BaselineSpec(
        ref=33, label="Xue et al. [33]", classical_sig=True, validate="policy+sig", authorize="policy",
        adapt="central", audit="sig_hash", onchain="hash+sig", grounded="table-iv",
        note="Controllable, publicly auditable main-auxiliary redactable blockchain (TDSC 2026). PDF not in Scheme/."),
    # ---- Exp. 2 (authorization) --------------------------------------------------------------
    "dong2024": BaselineSpec(
        ref=15, label="Dong et al. [15]", classical_sig=True, validate="sig", authorize="maabe_threshold",
        adapt="central", audit=None, onchain="hash", grounded="table-iv",
        note="CH + multi-authority ABE (HCC 2024). TODO-VERIFY authorization cost; PDF not in Scheme/."),
    "li2025_dch": BaselineSpec(
        ref=1, label="Li et al. [1] (Improved DCH)", classical_sig=True, validate="sig", authorize="dch_approve",
        adapt="threshold", audit=None, onchain="hash", grounded="pdf",
        note="t full nodes approve by checking signatures of tx and tx', then run DCH.Collision shares. "
             "See Scheme/1_Improved-DCH_Li2025."),
    # ---- Exp. 3/4 (audit) --------------------------------------------------------------------
    "eaq_vrbc2025": BaselineSpec(
        ref=13, label="EAQ-VRBC [13] (cited as 'VRBC')", classical_sig=True, validate="sig", authorize="none",
        adapt="central", audit="vds_per_record", onchain="hash", grounded="pdf",
        note="Per-record identity-based tags + RSA-accumulator non-membership (freshness); trusted SM redacts. "
             "See Scheme/3_EAQ-VRBC_Zhang2025."),
    "miao2026": BaselineSpec(
        ref=20, label="Miao et al. [20]", classical_sig=True, validate="sig", authorize="none",
        adapt="central", audit="light", onchain="hash", grounded="table-iv",
        note="Verifiable & redactable blockchain with lightweight storage and permission supervision "
             "(Information 2026). TODO-VERIFY; PDF not in Scheme/."),
}

EXP_BASELINES = {
    1: ["huang2021", "wang2024", "liu2026_etch", "xue2026_mainaux"],
    2: ["liu2026_etch", "dong2024", "li2025_dch"],
    3: ["eaq_vrbc2025", "xue2026_mainaux", "miao2026"],
    4: ["eaq_vrbc2025", "miao2026", "xue2026_mainaux"],
    5: ["huang2021", "wang2024", "liu2026_etch", "xue2026_mainaux"],
}


def make_baseline(key, ledger, pq_adapted=True):
    return PerRequestBaseline(SPECS[key], ledger, pq_adapted=pq_adapted)
