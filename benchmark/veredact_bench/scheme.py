"""The contract every system under test implements — VeRedact-PQ and the four re-implemented baselines.

This interface is the fairness mechanism. The experiment runners talk only to Scheme, so no system is
driven through a code path the others do not share, timed at a boundary the others do not use, or
handed a workload the others did not receive. docs/experiments.md states the contract in prose; this
file is where it is enforced.

Load-bearing decisions (same as the conference artefact ZK-Redact):
  * redact() takes a LIST. VeRedact-PQ batches (ABRRR + BIMC); the baselines process the list one request
    at a time, which makes them the natural B = 1 point of the same axis.
  * Results separate crypto_ms from ledger_ms and never sum them. Chameleon-hash adaptation is per
    affected batch/request; only blockchain-side work amortises. One number would hide which improved.
  * capabilities() is reported by the implementation, and the capability matrix printed beside every
    performance table is generated from it — it cannot drift from the code.
  * auth_cost() counts what one authorization DID (signature/proof verifications, consensus blocks,
    round trips), so a latency can be re-derived under another configuration instead of taken on trust.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


class NotSupported(Exception):
    """The scheme's own paper defines no such operation (e.g. S27 ETCH has no audit protocol).
    Runners record it in the capability column; they never synthesise the operation on its behalf."""


# ----------------------------------------------------------------------------------------- capabilities
@dataclass(frozen=True)
class Capabilities:
    pq_security: bool            # every security-critical primitive post-quantum (manuscript Table I col. 1)
    distributed_auth: bool       # no single entity can authorize unilaterally
    policy_control: bool         # rights evaluated against a policy, not mere key possession
    batch_redaction: bool        # blockchain-side cost amortised across independent requests
    private_verification: bool   # authorization without revealing requester attributes
    verifiable_auditing: bool    # auditor can verify redaction evidence
    state_freshness_check: bool  # revalidates the authorized state at execution time
    consensus_bound_auth: bool   # authorization itself needs ledger agreement


@dataclass
class AuthCost:
    signature_verifications: int = 0
    proof_verifications: int = 0
    signatures_generated: int = 0
    consensus_blocks: int = 0
    round_trips: int = 0


# ----------------------------------------------------------------------------------------- shared data
@dataclass(frozen=True)
class Transaction:
    tid: bytes
    payload: bytes
    owner: int
    policy: int
    ts: int


@dataclass(frozen=True)
class RedactionRequest:
    """One entry of the shared request trace (identical, in identical order, for every system)."""
    seq: int
    requester: int
    tid: bytes
    new_payload: bytes
    arrival_s: float
    fault: str = ""  # "" = valid; else the injected fault class (sig, zk, policy, stale, replay, absent)


@dataclass
class Dataset:
    seed: int
    transactions: list
    requesters: int
    policies: int
    trace: list
    dataset_id: str  # digest of everything above (recorded in every result file)


# ----------------------------------------------------------------------------------------- results
@dataclass
class Authorization:
    request: RedactionRequest
    ok: bool
    crypto_ms: float
    ledger_ms: float = 0.0
    reason: str = ""
    handle: object = None  # scheme-internal material passed on to redact()


@dataclass
class RedactionOutcome:
    seq: int
    ok: bool
    stale: bool = False
    reason: str = ""


@dataclass
class RedactionResult:
    outcomes: list  # RedactionOutcome per input request
    crypto_ms: float  # CH adaptation + Merkle/commitment work (off-chain, in-process)
    ledger_ms: float  # anchoring / finalisation (Besu when ledger.backend = besu)
    ch_adaptations: int  # chameleon-hash adaptations performed
    onchain_tx: list = field(default_factory=list)  # [(operation, gas_used)] from receipts
    finality: object = None  # Future -> (ledger_ms, gas) when anchoring is still in flight

    def wait(self):
        """Block until the ledger finalised this result; fills ledger_ms and onchain_tx."""
        if self.finality is not None:
            ms, gas = self.finality.result()
            self.ledger_ms += ms
            self.onchain_tx.append(("redaction_finalization", gas))
            self.finality = None
        return self


@dataclass
class AuditQuery:
    records: int
    deep: bool = False
    tamper: dict = field(default_factory=dict)  # seq -> fault class, for Exp. 4 fault injection


@dataclass
class AuditResult:
    semantics: str  # what the scheme actually audits (e.g. "redaction provenance", "ledger integrity")
    retrieval_ms: float  # service side: resolve + build evidence
    verify_ms: float  # auditor side
    evidence_bytes: int
    accepted: dict  # seq -> bool (per-record decision)


# ----------------------------------------------------------------------------------------- the contract
class Scheme(ABC):
    key: str  # matches config/schemes.toml and config/*.toml [experiments.*].systems

    @abstractmethod
    def capabilities(self) -> Capabilities: ...

    @abstractmethod
    def setup(self, dataset: Dataset) -> None:
        """Materialise the shared dataset into this scheme's native ledger form. NOT timed."""

    @abstractmethod
    def authorize(self, req: RedactionRequest) -> Authorization:
        """Decide whether one request is permitted (Exp. 2 boundary: admission -> decision)."""

    @abstractmethod
    def redact(self, batch: list) -> RedactionResult:
        """Execute authorized requests and commit them (Exp. 1/5 boundary: execution -> finalized)."""

    def audit(self, query: AuditQuery) -> AuditResult:
        raise NotSupported(f"{self.key}: its paper defines no audit protocol")

    def auth_cost(self) -> AuthCost:
        raise NotSupported(f"{self.key}: cannot count its authorization cost honestly")

    def teardown(self) -> None:
        pass
