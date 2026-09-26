# VeRedact-PQ: Scalable Post-Quantum Redaction with Multi-Party Authorization and Verifiable Auditing

**Rangsimann Sattayarom, Ratchanon Wongwitutai, Natthawat Tungsriworakan, Tagrid Chongkolrattanapond, Somchart Fugkeaw**

Sirindhorn International Institute of Technology, Thammasat University, Thailand
6622771747@g.siit.tu.ac.th, 6622780268@g.siit.tu.ac.th, 6622772364@g.siit.tu.ac.th, 6622781175@g.siit.tu.ac.th, somchart@siit.tu.ac.th

## Abstract

Redactable permissioned blockchains enable legitimate modification of committed transactions, but existing approaches face challenges in distributed authorization, privacy-preserving accountability, post-quantum security, and scalability under high redaction workloads. In particular, independently validating, authorizing, executing, and auditing each redaction can incur substantial cryptographic and committee overhead, while controlled modification must remain bound to the applicable policy and current ledger state. We propose *VeRedact-PQ*, a post-quantum authenticated and verifiable redaction framework for permissioned blockchains. VeRedact-PQ separates immutable transaction-policy bindings from redactable content and employs post-quantum authentication and zero-knowledge verification for privacy-preserving request validation. A workload-aware adaptive batching mechanism amortizes multi-party committee authorization while preserving request-level policy enforcement. For efficient execution, authorized modifications targeting the same transaction batch are coalesced into shared Merkle updates, requiring only one distributed post-quantum chameleon-hash adaptation per resulting batch-root transition. Cryptographic evidence binds request validation and committee authorization to the executed redaction, providing individual accountability despite batched processing. Finally, a sharded authenticated audit index supports privacy-preserving query-based verification using compact multiproofs and shared batch evidence, while expensive post-quantum zero-knowledge verification is reserved for challenged or forensic audits. VeRedact-PQ thereby provides an end-to-end post-quantum redaction workflow that amortizes authorization, authenticated-state update, redaction, and audit-verification costs while maintaining policy binding, distributed control, privacy, and verifiable accountability.

**Index Terms** — Permissioned Blockchain, Redactable Blockchain, Post-Quantum Chameleon Hash, Post-Quantum Security, Verifiable Redaction, Privacy-Preserving Auditing, Large-scale Transaction Processing.

## Introduction

Permissioned blockchains provide a shared and auditable ledger for multi-organization environments without requiring complete mutual trust. Their integrity fundamentally relies on cryptographic immutability: once a transaction is committed, unauthorized modification becomes detectable. Strict immutability, however, can conflict with legitimate enterprise requirements, including correction of erroneous records, removal of sensitive information for privacy or regulatory compliance, and controlled update of obsolete data \[9, 21, 22\]. Supporting such operations without undermining ledger integrity creates the fundamental problem of *controlled and accountable blockchain redaction*.

Redactable blockchains commonly employ chameleon hashes to modify committed data while preserving blockchain consistency \[1, 2, 6, 30\]. Subsequent studies have strengthened this model through fine-grained access control \[8, 15\], decentralized trapdoor management \[3, 19\], dynamic updates \[5, 16\], and threshold redaction \[27\]. Nevertheless, preserving the ledger commitment alone does not establish that a requester is authorized for a particular transaction, operation, policy, and current state. Moreover, because an authorized chameleon-hash collision preserves blockchain linkage, conventional ledger verification cannot by itself establish why a modification was permitted or whether the required authorization process was followed. Recent policy-based, traceable, and publicly auditable constructions improve accountability \[33, 34, 35\], but integrating request-level policy validation with distributed authorization and verifiable execution remains important for multi-organization redaction.

Privacy and long-term security further complicate this problem. Fine-grained and policy-hiding schemes can restrict redaction authority or conceal authorization policies \[4, 18, 31, 34\], while verifiable and auditable designs provide mechanisms for checking redaction integrity \[13, 20, 33\]. However, authorization may depend on sensitive credentials, roles, or policy attributes that should not be disclosed merely to prove eligibility, and auditors should not need access to the underlying sensitive transaction to verify a redaction. In parallel, lattice-based and quantum-resistant chameleon hashes have been investigated for redactable blockchains \[10, 11, 17, 37\]. Protecting only the chameleon-hash primitive, however, is insufficient for an end-to-end post-quantum workflow if requester authentication, private authorization, committee approval, or audit authentication still depends on classical cryptography.

Scalability is another major challenge. Existing studies have addressed scalable redaction \[14, 21, 26\], efficient data-structure updates \[23\], lightweight storage and verification \[20\], and robust threshold redaction \[27\]. Nevertheless, under high transaction and redaction volumes, ledger-wide target lookup, per-request policy verification, individual committee authorization, repeated Merkle updates, and independent chameleon-hash adaptations can collectively incur substantial overhead. Fixed or request-by-request processing also cannot adapt well to varying workloads, while batching must preserve individual policy enforcement so that an invalid request cannot inherit the authorization of valid requests. Similarly, independently verifying every redaction record can make large-scale auditing expensive. Efficient redactability therefore requires coordinated scalability across *request resolution, authorization, redaction execution, and auditing*, while retaining request-level accountability.

To address these challenges, we propose *VeRedact-PQ*, a post-quantum authenticated, scalable, and verifiable redaction framework for permissioned blockchains. VeRedact-PQ provides an end-to-end redaction workflow that separates request validation, multi-party authorization, controlled state modification, and privacy-preserving auditing. Rather than applying expensive cryptographic and committee operations independently to every request, the framework combines request-level policy enforcement with adaptive batch authorization, coalesced state updates, and query-scoped audit verification. Post-quantum mechanisms protect the security-critical authentication, private authorization, redaction, and audit paths, while compact attestations and authenticated-data-structure proofs avoid unnecessary repeated PQ processing. The resulting design preserves individual accountability from redaction request to auditable state transition while amortizing common operations under high-volume workloads. The main contributions are summarized as follows:

- **Post-Quantum Authenticated and Policy-Bound Redaction:** We design an end-to-end post-quantum redaction workflow comprising PQ requester authentication, Post-Quantum Zero-Knowledge (PQZK) private policy verification, $t$-of-$n$ PQ committee authorization, and distributed Post-Quantum Chameleon Hash (PQCH) redaction. The proposed Redaction-Aware Dual Commitment (RADC) separates the immutable transaction-policy binding from the redactable content state, ensuring that an authorized content modification cannot alter its protected policy context.

- **Scalable Resolution and Adaptive Authorization:** We develop a sharded authenticated lookup structure for efficient redaction-target resolution and an Adaptive Batch Round Redaction Request (ABRRR) mechanism for workload-aware multi-party authorization. Requests are independently validated before batching and represented by compact PQ-signed validation attestations, enabling batch authorization without repeating expensive PQZK verification.

- **Coalesced and Verifiable Batch Redaction:** We develop a Batch Incremental Merkle Commitment (BIMC) mechanism that coalesces authorized modifications within each transaction batch, allowing them to share Merkle authentication paths and incur only one distributed PQCH adaptation for the resulting batch-root transition. The Policy-Bound Batch Redaction Proof (PBRP) cryptographically binds request-level validation and committee authorization to the executed state transition, preserving individual verifiability under batched redaction.

- **Cost-Aware Post-Quantum Auditing:** We design a sharded Redaction Audit Index (RAI) for privacy-preserving verification of redaction integrity, history, authorization, policy compliance, scope, and freshness. Query-scoped Merkle multiproofs, shared batch evidence, and query-adaptive proof disclosure reduce routine verification and communication costs, while complete PQZK verification remains available for challenged or deep forensic audits.

## Related Work

**Table I.** Comparison of VeRedact-PQ with Representative Redactable Blockchain Schemes

| Scheme | PQ Security | Distributed/Threshold Auth. | Policy Control | Scalable/Batch Redaction | Private Verification | Verifiable Auditing |
|:--|:-:|:-:|:-:|:-:|:-:|:-:|
| Jia *et al.* [1] | ✗ | ✓ | ✗ | ✗ | ✗ | △ |
| Huang *et al.* [14] | ✗ | ✗ | △ | ✓ | ✓ | ✗ |
| VRBC [13] | ✗ | ✗ | △ | ✗ | △ | ✓ |
| Zhang *et al.* [5] | ✗ | △ | ✓ | △ | ✗ | ✓ |
| Dong *et al.* [15] | ✗ | ✓ | ✓ | ✗ | △ | △ |
| Wang *et al.* [17] | ✓ | ✗ | △ | ✗ | ✗ | ✗ |
| Miao *et al.* [20] | ✗ | △ | ✓ | △ | △ | ✓ |
| Liu *et al.* [27] | ✗ | ✓ | △ | ✓ | ✗ | △ |
| Xue *et al.* [33] | ✗ | △ | ✓ | △ | △ | ✓ |
| J. Xue *et al.* [34] | ✗ | △ | ✓ | ✗ | ✓ | ✓ |
| **VeRedact-PQ** | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |

✓: Supported; △: Partially supported; ✗: Not supported

### Distributed and Scalable Blockchain Redaction

Redactable blockchains commonly employ chameleon hashes to modify committed data while preserving blockchain consistency \[9\]. Subsequent studies extended this model to consortium blockchains \[2\] and decentralized redaction through distributed chameleon hashes and trapdoor management \[1, 3, 6, 19, 30\]. Multi-party chameleon hashing \[12\] and robust threshold redaction \[27\] further reduce dependence on a single redaction authority, while dynamic and controlled constructions support evolving redaction requirements \[5, 16, 36\].

Scalability has also been addressed through efficient update mechanisms, lightweight storage, specialized Merkle structures, and application-oriented redaction \[14, 20, 21, 23, 26\]. However, efficiency is typically optimized at a particular layer, whereas high-volume redaction incurs combined costs from target lookup, request validation, committee authorization, authenticated state updates, and chameleon-hash adaptation. VeRedact-PQ addresses these costs jointly through sharded lookup, adaptive request batching, coalesced Merkle updates, and one distributed PQCH adaptation per affected transaction-batch root transition.

### Policy-Controlled, Private, and Verifiable Redaction

Fine-grained redaction has been developed using attribute- and policy-based mechanisms \[8, 15\], while privacy-preserving and policy-hiding constructions restrict disclosure of sensitive authorization information \[4, 18, 31, 34\]. Other schemes strengthen traceability and accountability through dynamic policies, anonymous but accountable redaction, policy-compliant rewriting, and cross-chain accountability \[28, 29, 32, 35\]. Verifiable redaction has likewise been studied through efficient query and integrity auditing \[13\], lightweight verification and permission supervision \[20\], and publicly auditable architectures \[33\].

Despite these advances, policy validation, multi-party authorization, redaction execution, and auditing are often treated as separate functions. VeRedact-PQ instead binds them at request level: private policy eligibility is verified before batching, committee authorization is bound to an authenticated batch, and PBRP links this evidence to the executed state transition. A sharded RAI subsequently supports query-based auditing using compact multiproofs and shared batch evidence, preserving individual accountability without repeatedly processing complete redaction proofs.

### Post-Quantum Redactable Blockchains

Post-quantum redactable blockchain research has primarily focused on the chameleon-hash primitive. Existing approaches include quantum-resistant key-exposure-free chameleon hashing \[11\], lattice-based redactable blockchains \[10\], quantum-resistant redaction with trapdoor updates \[17\], and lattice-based policy- or identity-oriented chameleon hashes \[18, 37\]. These works provide important foundations for protecting controlled redaction against quantum adversaries.

However, a quantum-resistant chameleon hash alone does not provide an end-to-end post-quantum redaction workflow if authentication, authorization, committee approval, or auditing still relies on classical mechanisms. VeRedact-PQ therefore extends PQ protection across the security-critical workflow using PQ authentication, PQZK-based private policy validation, PQ multi-party authorization, and distributed PQCH redaction. To control overhead, expensive PQZK verification is performed only when required, while compact PQ-signed attestations and hash-based authenticated proofs support subsequent authorization and routine auditing.

Overall, VeRedact-PQ differs from existing work by jointly addressing *post-quantum security, scalable multi-party redaction, and privacy-preserving verifiability* across the complete redaction lifecycle rather than optimizing these properties independently.

As summarized in Table I, existing redactable blockchain schemes typically address only a subset of the requirements for secure and scalable enterprise redaction. Decentralized and threshold-based approaches strengthen distributed control \[1, 15, 27\], while policy-oriented schemes provide fine-grained or privacy-aware redaction authorization \[5, 34\]. Other works primarily improve scalability \[14, 20\] or verifiable auditing \[13, 33\]. Quantum-resistant schemes such as \[17\] protect the underlying redaction primitive, but do not jointly provide post-quantum authentication, private policy validation, distributed authorization, and audit verification. In contrast, VeRedact-PQ provides more comprehensive properties of the redaction lifecycle. It supports request-level PQ authentication and policy verification with distributed batch authorization, coalesced redaction execution, and privacy-preserving auditing. Importantly, this integration is cost-aware: expensive PQ verification is not repeatedly invoked across all stages, while authenticated batching, shared state updates, and query-scoped proofs amortize authorization, redaction, and auditing costs under high-volume workloads.

## Our Proposed VeRedact-PQ Scheme

This section presents the system model, threat model, and system process of our proposed VeRedact-PQ scheme.

### System Model

![System model of the proposed VeRedact-PQ framework](system_model.PNG)

**Fig. 1.** System model of the proposed VeRedact-PQ framework

As illustrated in Fig. 1, VeRedact-PQ considers a permissioned blockchain operated by multiple mutually accountable organizations. The blockchain stores enterprise transactions whose contents may subsequently require legitimate modification or removal according to predefined redaction policies. Rather than assigning the redaction capability to a single privileged authority, VeRedact-PQ distributes redaction authorization among an epoch-based committee and maintains cryptographic evidence that allows an authorized redaction to be independently verified. The system consists of the following entities.

**1) Data Owner (DO):** A data owner generates and submits transactions to the permissioned blockchain. Before submission, the DO signs the transaction to provide origin authentication and integrity. Each transaction is associated with its identifier, data type, timestamp, and applicable redaction policy. When permitted by the corresponding policy, the DO may also submit a redaction request for previously committed data.

**2) Authorized Requester (AR):** An authorized requester is an authenticated entity permitted to request modification or removal of a committed transaction. The requester submits a signed redaction request specifying the target transaction and requested modification. It also provides the information required to demonstrate compliance with the applicable redaction policy. The requester may coincide with the original data owner or may be another entity granted redaction rights by the consortium.

**3) Redaction Committee (RC):** The redaction committee consists of authorized consortium members that collectively govern the redaction capability. Committee membership is defined for an authorization epoch $e$, allowing the authorization structure to evolve over time. The committee members jointly participate in the distributed management of the post-quantum chameleon-hash trapdoor and authorize eligible redactions through threshold approval. Consequently, no individual committee member is intended to exercise the complete redaction capability independently.

**4) Validation and Policy Service (VPS):** The VPS validates incoming redaction requests before they become eligible for committee authorization. It authenticates the requester, retrieves the policy associated with the target transaction, verifies the requested redaction against the permitted scope and validity conditions, and verifies the corresponding policy-compliance zero-knowledge proof. Only successfully validated requests are admitted to the subsequent authorization process.

**5) Permissioned Blockchain Network (PBN):** The PBN is maintained by authenticated consortium nodes executing the underlying permissioned consensus protocol. It records transaction commitments, policy references, epoch information, redaction checkpoints, and verification metadata, including a node operating the audit service that returns altered or stale audit responses. Transaction batches are committed through Merkle roots and a post-quantum chameleon hash (PQCH), allowing an authorized modification to preserve the required ledger linkage while unauthorized modifications remain detectable. The blockchain additionally provides an immutable reference for redaction authorization and subsequent auditing.

**6) Auditor (AU):** An auditor is an authorized internal or external verifier responsible for examining the legitimacy of completed redactions. The auditor does not require access to the complete sensitive transaction content. Instead, it verifies the corresponding policy-bound redaction evidence, authenticated batch membership, committee authorization, and anchored blockchain state to determine whether the redaction was properly authorized and executed.

For scalable redaction processing, successfully validated requests are placed in a pending request queue. VeRedact-PQ employs the *Adaptive Batch Round Redaction Request (ABRRR)* mechanism to dynamically form a batch $B_e$ according to the observed request rate, queue state, and maximum waiting time. Each request remains individually policy validated before batching. The corresponding *Policy-Bound Batch Redaction Proof (PBRP)* cryptographically binds every validated request to its target transaction, policy state, and authorization epoch. The committee subsequently produces threshold authorization over the authenticated batch commitment, allowing common authorization and consensus operations to be amortized while retaining request-level accountability.

Accordingly, VeRedact-PQ separates three security responsibilities: *request-level validation*, performed before batching; *distributed redaction authorization*, performed by the epoch committee; and *post-redaction verification*, performed using PBRP and the blockchain-anchored state. This separation prevents an invalid request from inheriting the authorization of other requests in the same batch while enabling efficient and independently verifiable redaction in large-scale permissioned blockchain environments.

### Threat Model

VeRedact-PQ considers malicious or compromised participants in a permissioned blockchain. The main threats and security assumptions are defined as follows.

**1) Malicious Requester:** A malicious or compromised requester may submit unauthorized, malformed, or replayed redaction requests, or attempt to modify data outside the permitted policy scope. Each request must therefore be authenticated and independently validated against its associated redaction policy before authorization.

**2) Malicious Committee Members:** A subset of redaction committee members may collude to perform an unauthorized redaction or misuse their PQCH trapdoor shares. We assume that fewer than the required threshold of committee members are compromised; therefore, they cannot independently exercise the distributed redaction capability or generate valid threshold authorization.

**3) Malicious Blockchain Participant:** A compromised consortium node may attempt to alter, remove, or inject transaction or redaction information. VeRedact-PQ assumes that the underlying permissioned blockchain satisfies its prescribed consensus fault-tolerance condition.

**4) Batch-Manipulation Adversary:** An adversary may attempt to insert an invalid request into an authorized batch, replace a validated request, or reuse authorization evidence. PBRP binds each validated request to its target transaction, policy state, and authorization epoch, making such manipulation detectable.

**5) Privacy-Curious Auditor:** An auditor or consortium participant may attempt to infer sensitive transaction or authorization information from verification evidence. Zero-knowledge proofs and cryptographic commitments enable policy and redaction verification without revealing unnecessary sensitive information.

**6) Quantum-Capable Adversary:** The adversary may possess quantum-computing capabilities. VeRedact-PQ therefore relies on post-quantum chameleon hashing and post-quantum digital signatures for security-critical operations.

We assume that the adversary cannot break the underlying post-quantum cryptographic assumptions, forge valid signatures, find hash collisions, or generate a valid zero-knowledge proof for a false statement except with negligible probability. Compromise of the committee threshold, violation of the blockchain consensus assumption, denial-of-service attacks, endpoint compromise, and implementation-level side-channel attacks are outside the scope of this work.

### System Process

The VeRedact-PQ framework operates through 6 sequential phases where its details are described below. Table <a href="#tab:notation" data-reference-type="ref" data-reference="tab:notation">[tab:notation]</a> summarizes the major notations used throughout the framework.

#### Phase 1: System Setup

This phase initializes the cryptographic parameters, registered entities, redaction policies, and distributed redaction authority required by VeRedact-PQ. Let $\lambda$ denote the security parameter and $e$ denote the current authorization epoch.

**Step 1: Global Parameter Setup.** Given the security parameter $1^\lambda$, the consortium initializes the cryptographic primitives and generates the global public parameters

$$
PP={(\lambda,H,\mathsf{PQCH},\mathsf{PQSIG},
\mathsf{ZKP},\mathsf{Merkle})}
\tag{1}
$$

where $H$ is a post-quantum-secure hash function, $\mathsf{PQCH}$ denotes the post-quantum chameleon-hash scheme, $\mathsf{PQSIG}$ denotes the post-quantum digital-signature scheme, $\mathsf{ZKP}$ denotes the zero-knowledge proof system, and $\mathsf{Merkle}$ denotes the authenticated Merkle-tree construction. The public parameters $PP$ are made available to all registered participants.

**Step 2: Entity Registration and Key Generation.** Each participating entity $U_i$, including data owners, authorized requesters, committee members, the Validation and Policy Service (VPS), and auditors, registers with the permissioned blockchain and generates a post-quantum signature key pair

$$
(pk_i,sk_i)\leftarrow
\mathsf{PQSIG.KeyGen}(1^\lambda)
\tag{2}
$$

The tuple $(ID_i,Role_i,pk_i)$ is recorded in the consortium membership registry, while $sk_i$ is retained privately by $U_i$. In particular, the key pair of the VPS is denoted by $(pk_V,sk_V)$; $sk_V$ is used to issue validation attestations in Phase 3, and $pk_V$ is used to verify them in Phases 4 and 6.

**Step 3: Redaction Policy Registration.** For each supported transaction or data class, the consortium defines a redaction policy $P_j$ specifying the authorized requester roles, permitted redaction operations, applicable conditions, and validity period. The policy state is committed as

$$
C_{P_j}=H(PID_j\parallel P_j\parallel v_j\parallel e)
\tag{3}
$$

where $PID_j$ and $v_j$ denote the policy identifier and version, respectively. The tuple $(PID_j,C_{P_j},v_j,e)$ is registered on-chain to provide an authenticated reference for subsequent policy verification.

**Step 4: Epoch Committee Formation.** At the beginning of epoch $e$, the consortium establishes an $n$-member redaction committee

$$
\mathcal{C}_e={(C_1,C_2,\ldots,C_n)}, \qquad t\leq n
\tag{4}
$$

where at least $t$ committee members are required to exercise the redaction capability. The committee configuration $(e,\mathcal{C}_e,t)$ is recorded on-chain, binding subsequent redaction authorization to the committee active during epoch $e$.

**Step 5: Distributed PQCH Trapdoor Setup.** The members of $\mathcal{C}_e$ jointly execute the distributed key generation algorithm of the PQCH scheme:

$$
(pk_{\mathrm{CH}},\{td_{e,k}\}_{k=1}^{n})
\leftarrow
\mathsf{PQCH.DKeyGen}(PP,\mathcal{C}_e,t)
\tag{5}
$$

where $pk_{\mathrm{CH}}$ is the public chameleon-hash key and $td_{e,k}$ denotes the trapdoor share held by committee member $C_k$. No individual committee member possesses the complete redaction trapdoor, and at least $t$ authorized members are required to exercise the distributed redaction capability.

**Step 6: Post-Quantum ZK Parameter Setup.** The consortium initializes a post-quantum zero-knowledge proof (PQZK) system for privacy-preserving policy-compliance verification. For the policy relation $\mathcal{R}_{P}$, the system generates

$$
(pp_{\mathrm{PQZK}},pk_{\mathrm{PQZK}},vk_{\mathrm{PQZK}})
\leftarrow
\mathsf{PQZK.Setup}(1^\lambda,\mathcal{R}_{P})
\tag{6}
$$

where $pp_{\mathrm{PQZK}}$ denotes the public proof parameters, $pk_{\mathrm{PQZK}}$ and $vk_{\mathrm{PQZK}}$ denote the proving and verification parameters, respectively. The PQZK construction is assumed to provide completeness, soundness, and zero-knowledge security against quantum-capable adversaries. The PQZK instantiation is assumed to employ a transparent (trapdoor-free) setup, and the resulting public and verification parameters are published on the PBN, whereas any prover-specific secret state, if required by the selected instantiation, is securely maintained by the corresponding prover.

#### Phase 2: Redaction-Aware Transaction Commitment

This phase authenticates submitted transactions and establishes a redaction-aware committed state for subsequent authorization, redaction, and auditing.

**Step 1: Transaction Submission and Authentication.** A registered data owner $DO_i$ prepares transaction $m_i$ with transaction identifier $TID_i$, data type $DT_i$, applicable redaction policy $PID_i$, and timestamp $ts_i$. The data owner generates

$$
\sigma_i \leftarrow
\mathsf{PQSIG.Sign}\left(
sk_i,H(TID_i\parallel m_i\parallel DT_i
\parallel PID_i\parallel ts_i)\right)
\tag{7}
$$

and submits

$$
TX_i=(TID_i,m_i,DT_i,PID_i,ts_i,\sigma_i)
\tag{8}
$$

The system verifies the data owner’s registration and signature before accepting the transaction.

**Step 2: Redaction-Aware Commitment Construction.** For each accepted transaction, the system generates a fresh nonce $n_i$ and transaction tag

$$
Tag_i=H(TID_i\parallel n_i\parallel ts_i)
\tag{9}
$$

VeRedact-PQ then applies the Redaction-Aware Dual Commitment (RADC), which separates immutable transaction-policy information from the redactable content:

$$
I_i=
H(TID_i\parallel ID_{DO_i}\parallel DT_i
\parallel PID_i\parallel ts_i\parallel Tag_i)
\tag{10}
$$

$$
D_i=H(m_i)
\tag{11}
$$

The corresponding authenticated transaction leaf is

$$
L_i=H(I_i\parallel D_i\parallel\sigma_i)
\tag{12}
$$

Hence, a subsequent authorized redaction may change $D_i$ while the transaction-policy binding $I_i$ remains unchanged.

**Step 3: Merkle and PQCH Batch Commitment.** Authenticated leaves are grouped into batch $\mathcal{T}_b={L_1,\ldots,L_N}$ and committed through

$$
MR_b=\mathsf{Merkle.Root}(L_1,\ldots,L_N)
\tag{13}
$$

followed by the post-quantum chameleon-hash commitment

$$
CH_b=
\mathsf{PQCH.Hash}(pk_{\mathrm{CH}},MR_b,r_b)
\tag{14}
$$

where $r_b$ is fresh randomness. The Merkle structure retains the authentication information required for subsequent incremental batch updates. Thus, when multiple authorized redactions affect the same batch, BIMC can update only the affected Merkle paths rather than reconstructing the complete tree.

**Step 4: State Anchoring and Scalable Redaction Lookup Index.** The system records the authenticated batch checkpoint

$$
A_b=(b,CH_b,MR_b,e,v_b,ts_b,\sigma_b).
\tag{15}
$$

To support efficient transaction resolution over large-scale blockchain workloads, VeRedact-PQ constructs a *Sharded Authenticated Redaction Lookup Index (SA-RLI)*. For each transaction, the corresponding lookup entry is defined as

$$
E_i=
(Tag_i,b,pos_i,PID_i,v_b,e,I_i,D_i,ptr_i)
\tag{16}
$$

where $ptr_i$ references the authentication information required to verify the corresponding transaction state.

To determine the location of $E_i$ within the sharded index, the corresponding shard and bucket are computed as

$$
sid_i=H_1(Tag_i)\bmod S
\tag{17}
$$

$$
bid_i=H_2(Tag_i)\bmod B
\tag{18}
$$

where $S$ and $B$ denote the numbers of index shards and buckets, respectively. Thus, $sid_i$ identifies the shard and $bid_i$ identifies the bucket in which $E_i$ is indexed.

Each shard maintains an authenticated root

$$
R_{sid}=
\mathsf{Merkle.Root}(E_{s,1},E_{s,2},\ldots,E_{s,n_s})
\tag{19}
$$

and all shard roots are further bound to a global index root

$$
R_{\mathrm{RLI}}=
\mathsf{Merkle.Root}(R_1,R_2,\ldots,R_S)
\tag{20}
$$

A lightweight Cuckoo filter $CF_s$ is maintained for each shard to rapidly reject nonexistent transaction tags before accessing the authenticated index. Since the filter is used only for candidate screening, any positive result is subsequently validated against the corresponding authenticated SA-RLI entry.

Consequently, a redaction request can resolve $Tag_i$ directly to its batch, leaf position, policy, version, and committed RADC state without scanning blockchain transactions. Index insertion and update are localized to the affected shard, while the hierarchical authentication structure enables independently verifiable lookup results suitable for high-volume transaction processing.

#### Phase 3: Redaction Request Authentication and PQZK-Based Policy Verification

This phase validates incoming redaction requests through a staged verification process that rejects invalid requests before invoking costly post-quantum proof verification. VeRedact-PQ first performs low-cost freshness and SA-RLI lookup checks, followed by post-quantum requester authentication, public policy validation, and PQZK-based private policy verification. Successfully validated requests receive a post-quantum validation attestation and are admitted to the subsequent ABRRR authorization phase.

**Step 1: Request Admission and Scalable Transaction Resolution.** An authorized requester $U_r$ submits a redaction request

$$
R_i=(ID_r,TID_i,op_i,D_i',e,ts_r,n_r)
\tag{21}
$$

where $op_i$ denotes the requested redaction operation, $D_i'$ is the commitment to the proposed redacted content, $e$ is the current epoch, $ts_r$ is the request timestamp, and $n_r$ is a fresh nonce. The system first checks the request format, timestamp, nonce, and epoch to reject malformed, stale, or replayed requests.

For an admissible request, the system derives the privacy-preserving lookup token and identifies the corresponding SA-RLI shard and bucket:

$$
\tau_i=\mathsf{PRF}_{K_{\mathrm{idx}}}(TID_i)
\tag{22}
$$

$$
sid_i=H_1(\tau_i)\bmod S
\tag{23}
$$

$$
bid_i=H_2(\tau_i)\bmod B
\tag{24}
$$

The Cuckoo filter $CF_{sid_i}$ is first queried to rapidly reject nonexistent targets. For a positive candidate, the authenticated SA-RLI entry is retrieved as

$$
E_i=
(\tau_i,Tag_i,b,pos_i,PID_i,v_b,e_i,I_i,D_i,ptr_i)
\tag{25}
$$

The entry is verified against the corresponding shard root $R_{sid_i}$ and global index root $R_{\mathrm{RLI}}$. Using $ptr_i$, the system further verifies that the referenced transaction leaf is consistent with the committed Merkle root $MR_b$. The request is thereby resolved to its exact transaction batch, position, policy, version, and current RADC state $(I_i,D_i)$ without scanning the blockchain.

**Step 2: Post-Quantum Requester Authentication.** The requester authenticates the submitted request using its post-quantum signing key:

$$
\sigma_i^{R}\leftarrow
\mathsf{PQSIG.Sign}(sk_r,H(R_i))
\tag{26}
$$

The validation service accepts the requester only if

$$
\mathsf{PQSIG.Verify}
(pk_r,H(R_i),\sigma_i^{R})=1
\tag{27}
$$

where $pk_r$ is obtained from the consortium membership registry. Post-quantum signature verification is performed only after successful request admission and target resolution, avoiding unnecessary cryptographic processing for malformed or nonexistent requests.

**Step 3: Public Policy and State Validation.** Using $PID_i$ obtained from the authenticated SA-RLI entry, the validation service retrieves the applicable policy $P_i$, policy version $v_i$, and committed policy state $C_{P_i}$. Its integrity is verified as

$$
C_{P_i}\stackrel{?}{=}
H(PID_i\parallel P_i\parallel v_i\parallel e_i)
\tag{28}
$$

The service directly evaluates non-sensitive conditions, including whether $op_i$ is permitted by $P_i$, whether the policy and request are valid for epoch $e_i$, and whether $v_b$ and $D_i$ correspond to the current committed transaction state. Performing these public checks outside the PQZK relation reduces unnecessary proof complexity.

**Step 4: PQZK-Based Private Policy Verification.** Only requests passing the preceding checks invoke the PQZK mechanism. The requester proves possession of the private credentials and authorization attributes required by $P_i$ without revealing them. The public statement is

$$
x_i=
(TID_i,I_i,D_i,D_i',C_{P_i},op_i,b,v_b,e_i)
\tag{29}
$$

while the private witness $w_i$ contains the requester credentials, private authorization attributes, and sensitive policy evidence.

The policy relation $\mathcal{R}_{P}$ satisfies

$$
\mathcal{R}_{P}(x_i,w_i)=1
\tag{30}
$$

only when the hidden witness satisfies the required private policy conditions and authorizes $op_i$ for the specified transaction state and epoch. The requester generates

$$
\pi_i^{PQ}\leftarrow
\mathsf{PQZK.Prove}
(pk_{\mathrm{PQZK}},x_i,w_i)
\tag{31}
$$

and the validation service accepts only if

$$
\mathsf{PQZK.Verify}
(vk_{\mathrm{PQZK}},x_i,\pi_i^{PQ})=1
\tag{32}
$$

Binding $(D_i,b,v_b,e_i)$ to the public statement prevents a valid proof from being reused for a stale or previously modified transaction state.

**Step 5: Validated Request Commitment and Attestation.** For every request passing all preceding checks, VeRedact-PQ constructs a policy- and state-bound validated-request commitment

$$
\begin{split}
    C_i^{VR}= H(RID_i\parallel TID_i\parallel I_i\parallel D_i\parallel D_i' \parallel C_{P_i} \parallel \\op_i\parallel b\parallel v_b \parallel e_i\parallel H(\pi_i^{PQ})) 
\end{split}
\tag{33}
$$

where $RID_i$ uniquely identifies the redaction request.

The validation service then issues a post-quantum validation attestation over the accepted request:

$$
\alpha_i=
\mathsf{PQSIG.Sign}
\left(sk_V,
H(RID_i\parallel C_i^{VR}\parallel e_i)\right)
\tag{34}
$$

where $sk_V$ denotes the registered signing key of the validation service. The attestation enables subsequent committee members and auditors to verify that $C_i^{VR}$ corresponds to a request that successfully passed the Phase 3 validation procedure without requiring them to repeat the complete PQZK verification.

The resulting validated request is represented as

$$
VR_i=
(RID_i,C_i^{VR},b,pos_i,PID_i,v_b,e_i,
\sigma_i^{R},H(\pi_i^{PQ}),\alpha_i)
\tag{35}
$$

The complete PQZK proof $\pi_i^{PQ}$ remains available as supporting evidence when explicit proof verification is required, while its hash is included in the compact validated-request representation.

Only requests that successfully pass SA-RLI resolution, post-quantum requester authentication, public policy and state validation, and PQZK verification are admitted to the pending validated-request queue $\mathcal{Q}_e$. Consequently, each $VR_i$ is independently bound to its authenticated requester, target transaction, applicable policy, current committed state, PQZK evidence, and authorization epoch. Phase 4 subsequently applies ABRRR to these attested requests and constructs authenticated batch evidence for multi-party committee authorization.

#### Phase 4: Adaptive Batch Formation and Multi-Party Committee Authorization

This phase adaptively groups independently validated redaction requests and obtains distributed authorization from the epoch committee. VeRedact-PQ employs the *Adaptive Batch Round Redaction Request (ABRRR)* mechanism to adjust batch formation according to the current request workload and bounded waiting time. Rather than repeating the PQZK verification performed in Phase 3, the committee verifies the corresponding post-quantum validation attestations and authorizes a single authenticated commitment covering all eligible requests in the batch.

**Step 1: Adaptive Batch Formation.** Let $\mathcal{Q}_e$ denote the queue of validated requests during epoch $e$, $\lambda_e$ the observed request arrival rate, and $T_{\max}$ the maximum allowable waiting time. ABRRR dynamically determines the target batch size as

$$
\widehat{B}_e=
f(\lambda_e,|\mathcal{Q}_e|,T_{\max})
\tag{36}
$$

$$
B_e^{*}=
\min\left\{B_{\max},\max\{B_{\min},\widehat{B}_e\}\right\}
\tag{37}
$$

where $B_{\min}$ and $B_{\max}$ denote the minimum and maximum permitted batch sizes. A batch is formed when either $B_e^{*}$ eligible requests are available or the oldest eligible request reaches $T_{\max}$. Thus, larger batches are formed under heavy workloads to amortize authorization overhead, whereas timeout-triggered smaller batches bound waiting latency under light workloads.

The resulting authorization batch is

$$
\mathcal{B}_e=
{(VR_1,VR_2,\ldots,VR_m)},
\qquad 1\leq m\leq B_e^{*}
\tag{38}
$$

**Step 2: Attestation and State-Freshness Verification.** Before batch authorization, each $VR_i\in\mathcal{B}_e$ is checked against its Phase 3 validation attestation. The committee verifies

$$
\mathsf{PQSIG.Verify}
\left(
pk_V,
H(RID_i\parallel C_i^{VR}\parallel e_i),
\alpha_i
\right)=1
\tag{39}
$$

where $pk_V$ is the registered public key of the validation service. This confirms that the request successfully passed the Phase 3 authentication, policy, state, and PQZK verification procedure without requiring the committee to repeat the complete PQZK verification.

Because transaction state may change between validation and batch authorization, the current state is additionally checked as

$$
(D_i,v_b,e_i)
\stackrel{?}{=}
(D_i^{cur},v_b^{cur},e^{cur})
\tag{40}
$$

Any request with an invalid attestation or stale state is excluded from the batch and must be revalidated before subsequent authorization.

**Step 3: PQZK-Bound Batch Commitment.** For every eligible request, VeRedact-PQ constructs a compact authenticated request leaf

$$
\eta_i=
H(RID_i\parallel C_i^{VR}\parallel H(\pi_i^{PQ})
\parallel\alpha_i\parallel b\parallel v_b\parallel e_i)
\tag{41}
$$

The request leaves are aggregated into the authenticated validation root

$$
R_e^{VR}=
\mathsf{Merkle.Root}
(\eta_1,\eta_2,\ldots,\eta_m)
\tag{42}
$$

Although the individual PQZK proofs are not cryptographically aggregated into a single PQZK proof, $R_e^{VR}$ provides a compact authenticated commitment to the independently verified PQZK evidence and validation attestations of all requests in the batch.

The resulting ABRRR batch commitment is

$$
C_e^{B}=
H(BID_e\parallel e\parallel m
\parallel R_e^{VR}\parallel ts_e)
\tag{43}
$$

where $BID_e$ is the unique batch identifier and $ts_e$ denotes the batch-formation timestamp.

**Step 4: Multi-Party Committee Authorization.** The active redaction committee $\mathcal{C}_e$ verifies the batch identifier, epoch, validation root, and batch commitment. Each approving committee member $C_k$ produces a post-quantum authorization signature over the batch commitment:

$$
\sigma_{e,k}^{B}
\leftarrow
\mathsf{PQSIG.Sign}
(sk_{e,k},H(C_e^{B}\parallel e))
\tag{44}
$$

A batch is authorized only when at least $t$ distinct committee members provide valid approvals:

$$
\mathcal{A}_e =
\left\{
(k,\sigma_{e,k}^{B})
\;\middle|\;
\mathsf{PQSIG.Verify}
\left(
pk_{e,k},
H(C_e^{B}\parallel e),
\sigma_{e,k}^{B}
\right)=1
\right\}
\tag{45}
$$

$$
|\mathcal{A}_e|\geq t
\tag{46}
$$

The resulting multi-party authorization evidence is

$$
Auth_e^{B}=
(BID_e,C_e^{B},R_e^{VR},
\mathcal{A}_e,e,ts_e)
\tag{47}
$$

This $t$-of-$n$ authorization distributes redaction authority across independent consortium members without assuming that the underlying post-quantum signature scheme natively supports threshold signatures.

**Step 5: Policy-Bound Authorization Evidence.** For each authorized request $VR_i\in\mathcal{B}_e$, the system generates a Merkle membership proof $MP_i^{B}$ demonstrating that $\eta_i$ is included in the committee-authorized validation root $R_e^{VR}$. The authorization component of the *Policy-Bound Batch Redaction Proof (PBRP)* is represented as

$$
PBRP_i^{auth}=
(RID_i,\eta_i,MP_i^{B},
R_e^{VR},C_e^{B},Auth_e^{B})
\tag{48}
$$

Consequently, an individual request remains independently traceable to the authenticated ABRRR batch and its $t$-of-$n$ committee authorization without requiring repeated PQZK verification or individual committee authorization for every request.

Only batches satisfying Eq. (46) proceed to Phase 5 for controlled redaction. Phase 5 subsequently combines $PBRP_i^{auth}$ with the actual RADC content-state transition, BIMC update, and PQCH redaction evidence to construct the final PBRP.

#### Phase 5: Authorized Batch Redaction and Verifiable State Update

This phase executes the ABRRR batch authorized in Phase 4. To amortize redaction cost, requests targeting the same transaction batch are coalesced so that multiple leaf modifications require only one BIMC root update and one distributed PQCH adaptation. The resulting state transition is bound to the Phase 4 authorization evidence to form the final PBRP. The complete procedure is summarized in Algorithm 1.

**Step 1: Request Grouping and State Validation.** Given an authorized batch $\mathcal{B}_e$, the system first verifies $Auth_e^{B}$ and $PBRP_i^{auth}$ and partitions the requests according to their underlying transaction batch:

$$
\mathcal{B}_e=
\bigcup_{b\in\Omega_e}\mathcal{B}_{e,b}
\tag{49}
$$

$$
\mathcal{B}_{e,b}=
{VR_i\in\mathcal{B}_e:\mathsf{batch}(VR_i)=b}
\tag{50}
$$

where $\Omega_e$ is the set of affected transaction batches.

Before execution, each request must satisfy

$$
(D_i,v_b,e_i)
\stackrel{?}{=}
(D_i^{cur},v_b^{cur},e^{cur})
\tag{51}
$$

A stale request is excluded and returned to Phase 3 for revalidation.

**Step 2: RADC State Transition.** For each valid request $VR_i\in\mathcal{B}_{e,b}$, the approved redaction $m_i\rightarrow m_i'$ updates only the redactable content state:

$$
D_i'=H(m_i'),\qquad I_i'=I_i
\tag{52}
$$

and produces the updated authenticated leaf

$$
L_i'=H(I_i\parallel D_i'\parallel\sigma_i')
\tag{53}
$$

Thus, the transaction-policy binding $I_i$ remains immutable while the authorized content commitment changes.

**Step 3: Coalesced BIMC and Distributed PQCH Adaptation.** For each affected transaction batch $b$, all leaf changes are processed jointly. Given the affected old and new leaf sets $\mathcal{L}_b$ and $\mathcal{L}_b'$ and their compact multiproof $MP_b^{multi}$, BIMC derives one updated root

$$
MR_b'=
\mathsf{BIMC.Update}
(MR_b,\mathcal{L}_b,\mathcal{L}_b',MP_b^{multi})
\tag{54}
$$

Hence, shared Merkle paths are processed once rather than independently for each redaction.

The committee then performs one distributed PQCH adaptation for $MR_b\rightarrow MR_b'$. Each participating member $C_k$ independently computes

$$
\delta_{b,k}\leftarrow
\mathsf{PQCH.PartAdapt}
(td_{e,k},MR_b,r_b,MR_b',BID_e)
\tag{55}
$$

As soon as $t$ valid shares are available, they are combined:

$$
r_b'\leftarrow
\mathsf{PQCH.Combine}
\left({\delta_{b,k}}_{k\in\mathcal{T}_b}\right),
\qquad |\mathcal{T}_b|\geq t
\tag{56}
$$

The adaptation is accepted only if

$$
\begin{split}
\mathsf{PQCH.Hash}(pk_{\mathrm{CH}},MR_b,r_b)
=\\
\mathsf{PQCH.Hash}(pk_{\mathrm{CH}},MR_b',r_b')
=
CH_b
\end{split}
\tag{57}
$$

Adaptation shares and distinct affected batches can be processed in parallel. Consequently, $k$ redactions within the same transaction batch incur one BIMC update and one PQCH adaptation rather than $k$ independent root adaptations.

**Step 4: Authenticated State Update.** After successful adaptation, the batch version is advanced as

$$
v_b'=v_b+1
\tag{58}
$$

The affected SA-RLI entries are updated from $(D_i,v_b,ptr_i)$ to $(D_i',v_b',ptr_i')$. Only affected index shards $\Omega_S$ are recomputed, yielding

$$
R_{\mathrm{RLI}}'=
\mathsf{Merkle.Root}(R_1^{*},\ldots,R_S^{*})
\tag{59}
$$

$$
R_s^{*}=
\begin{cases}
R_s', & s\in\Omega_S\\
R_s,  & s\notin\Omega_S
\end{cases}
\tag{60}
$$

The updated authenticated checkpoint is

$$
A_b'=
(b,CH_b,MR_b',R_{\mathrm{RLI}}',
e,v_b',ts_b',\sigma_b')
\tag{61}
$$

**Step 5: PBRP and Redaction Record Generation.** For each successfully executed request, the final PBRP binds the Phase 4 authorization evidence to the resulting state transition:

$$
\begin{split}
PBRP_i=
PBRP_i^{auth},I_i,D_i,D_i',b,v_b,v_b',MR_b,\\
MR_b',CH_b,e,BID_e)
\end{split}
\tag{62}
$$

The corresponding audit record is

$$
\begin{split}
RR_i=
(RID_i,TID_i,BID_e,PID_i,D_i,D_i',\\
v_b,v_b',H(PBRP_i),ts_i^{red})
\end{split}
\tag{63}
$$

Only $H(PBRP_i)$ is retained in the compact redaction record, while the complete proof remains available as supporting evidence for Phase 6 auditing.

Algorithm 1 summarizes the execution. It exposes the main optimization of VeRedact-PQ: authorization is performed once per ABRRR batch, common Merkle paths are coalesced by BIMC, and PQCH adaptation is performed once per affected transaction batch with parallel threshold-share generation.

**Algorithm 1.** Authorized Batch Redaction and Verifiable State Update

```text
Require: Authorized batch B_e, authorization evidence Auth_e^B,
         states {MR_b, r_b, v_b}, threshold t
Ensure:  Updated checkpoints {A_b'} and redaction records {RR_i}

 1: Verify Auth_e^B and partition B_e into {B_{e,b}} for b ∈ Ω_e
 2: for all b ∈ Ω_e in parallel do
 3:     L_b ← ∅,  L_b' ← ∅
 4:     for all VR_i ∈ B_{e,b} do
 5:         if (D_i, v_b, e_i) ≠ (D_i^cur, v_b^cur, e^cur) then
 6:             Reject VR_i and return for revalidation
 7:         else
 8:             D_i' ← H(m_i'),  I_i' ← I_i
 9:             L_i' ← H(I_i ‖ D_i' ‖ σ_i')
10:             L_b  ← L_b  ∪ {L_i}
11:             L_b' ← L_b' ∪ {L_i'}
12:         end if
13:     end for
14:     MR_b' ← BIMC.Update(MR_b, L_b, L_b', MP_b^multi)
15:     for all C_k ∈ C_e in parallel do
16:         δ_{b,k} ← PQCH.PartAdapt(td_{e,k}, MR_b, r_b, MR_b', BID_e)
17:     end for
18:     Collect valid shares T_b until |T_b| ≥ t
19:     r_b' ← PQCH.Combine({δ_{b,k}} for k ∈ T_b)
20:     if PQCH.Hash(pk_CH, MR_b', r_b') ≠ CH_b then
21:         Abort update for batch b
22:     else
23:         v_b' ← v_b + 1
24:         Update affected SA-RLI entries and roots
25:         Construct updated checkpoint A_b'
26:         for all executed VR_i ∈ B_{e,b} do
27:             Construct PBRP_i using Eq. (62)
28:             Construct RR_i using Eq. (63)
29:         end for
30:     end if
31: end for
32: return {A_b'} for b ∈ Ω_e, {RR_i} for VR_i ∈ B_e
```

The resulting PBRP provides a verifiable link from the individually validated request and Phase 4 committee authorization to the executed RADC transition and the coalesced BIMC/PQCH state update. The redaction records ${RR_i}$ are subsequently indexed by RAI in Phase 6 for privacy-preserving query-based auditing.

#### Phase 6: Post-Quantum Privacy-Preserving Query-Based Redaction Auditing

This phase enables authorized auditors to selectively inspect and verify redaction records without accessing the underlying sensitive transaction contents. To maintain post-quantum security without introducing excessive audit overhead, VeRedact-PQ combines a sharded Redaction Audit Index (RAI), query-scoped Merkle multiproofs, post-quantum signatures, and compact PBRP evidence. Shared authorization evidence is verified once per ABRRR batch, while expensive PQZK verification is reserved for challenged or deep audits.

**Step 1: Authenticated Redaction Audit Index Construction.** For each redaction record $RR_i$ generated in Phase 5, the system derives a privacy-preserving audit token

$$
\tau_i^{A}=
\mathsf{PRF}_{K_A}(TID_i)
\tag{64}
$$

and constructs the compact audit entry

$$
\begin{split}
E_i^{A}=
(\tau_i^{A},RID_i,BID_e,PID_i,e,
v_b,v_b',\\
H(PBRP_i),ts_i^{red},ptr_i^{A})
\end{split}
\tag{65}
$$

where $ptr_i^{A}$ references the complete PBRP and supporting evidence. The content commitments and large cryptographic objects need not be duplicated in the index and are retrieved only when required by the audit query.

For scalability, RAI is partitioned into $S_A$ authenticated shards:

$$
sid_i^{A}=H_A(\tau_i^{A})\bmod S_A
\tag{66}
$$

$$
R_{\mathrm{RAI}}=
\mathsf{Merkle.Root}(R_1^{A},\ldots,R_{S_A}^{A})
\tag{67}
$$

Insertion of a new redaction record therefore modifies only its corresponding shard and the authentication path to the global root, rather than reconstructing the complete audit index.

At the end of each epoch, the system creates a compact audit checkpoint

$$
CP_e^{A}=
H(e\parallel R_{\mathrm{RAI}}\parallel v_A\parallel ts_e)
\tag{68}
$$

which is anchored to the permissioned blockchain. The checkpoint supports freshness and historical verification without requiring an auditor to traverse all subsequent audit states.

**Step 2: PQ-Authenticated Audit Query and Resolution.** An authorized auditor $AU_j$ submits

$$
Q_j^{A}=
(QID_j,qtype_j,\phi_j,scope_j,e_j,
[t_s,t_e],n_j,ts_j)
\tag{69}
$$

where $qtype_j$ specifies an integrity, history, authorization, policy-compliance, scope, freshness, batch-membership, or epoch/time query. The query is authenticated using

$$
\sigma_j^{A}\leftarrow
\mathsf{PQSIG.Sign}(sk_{AU_j},H(Q_j^{A}))
\tag{70}
$$

After verifying the signature and query freshness, the audit service resolves the relevant authenticated RAI entries:

$$
\mathcal{R}_{Q_j}
=
\{E_i^{A}:E_i^{A}\models Q_j^{A}\}
\tag{71}
$$

Thus, the auditor does not scan the complete blockchain or redaction history.

**Step 3: Compact Query-Scoped Evidence Generation.** For the matched records, the audit service generates a single query-scoped Merkle multiproof

$$
MP_{Q_j}^{A}
\leftarrow
\mathsf{Merkle.MultiProof}
(\mathcal{R}_{Q_j},R_{\mathrm{RAI}})
\tag{72}
$$

thereby sharing common authentication nodes among multiple returned records.

The matched records are further grouped by their ABRRR batch identifiers:

$$
\Omega_{Q_j}^{B}
=
\left\{
BID_e \mid E_i^{A}\in\mathcal{R}_{Q_j}
\right\}
\tag{73}
$$

For each distinct $BID_e$, the shared evidence $(R_e^{VR},C_e^{B},Auth_e^{B})$ is returned only once. The service then selects only the PBRP components required by the query:

$$
\Pi_{Q_j}=
\mathsf{SelectEvidence}
(qtype_j,\mathcal{R}_{Q_j},{PBRP_i})
\tag{74}
$$

For example, an authorization query requires batch-membership and committee-authorization evidence, whereas a scope query requires the RADC transition $(I_i,D_i,D_i')$. This query-adaptive disclosure avoids transmitting and processing complete PBRP objects when they are unnecessary.

The audit service authenticates the response using its post-quantum signature

$$
\begin{split}
\sigma_{Resp}^{A}\leftarrow
\mathsf{PQSIG.Sign}
\left(
sk_A,
H(QID_j\parallel H(Ans_j)\parallel\\
R_{\mathrm{RAI}}\parallel v_A\parallel ts_A)
\right)
\end{split}
\tag{75}
$$

The resulting response is

$$
\begin{split}
Resp_j^{A}=
(QID_j,Ans_j,\mathcal{R}_{Q_j},
MP_{Q_j}^{A},\Pi_{Q_j},
R_{\mathrm{RAI}},\\
v_A,ts_A,\sigma_{Resp}^{A})
\end{split}
\tag{76}
$$

**Step 4: Cost-Aware Post-Quantum Audit Verification.** The auditor first verifies $\sigma_{Resp}^{A}$ and the anchored RAI checkpoint, followed by the single query-scoped multiproof $MP_{Q_j}^{A}$. Shared ABRRR authorization evidence is verified only once for each distinct $BID_e\in\Omega_{Q_j}^{B}$ rather than once for every returned record.

For each individual redaction, only the PBRP components required by $qtype_j$ are subsequently checked. The verification chain is

$$
\begin{split}
VR_i
\Rightarrow
PBRP_i^{auth}
\Rightarrow
(D_i\rightarrow D_i')
\Rightarrow\\
(MR_b\rightarrow MR_b')
\Rightarrow CH_b
\end{split}
\tag{77}
$$

When state-transition verification is required, the auditor checks $I_i'=I_i$

$$
\begin{split}
\mathsf{PQCH.Hash}(pk_{\mathrm{CH}},MR_b,r_b)
=\\
\mathsf{PQCH.Hash}(pk_{\mathrm{CH}},MR_b',r_b')
=CH_b
\end{split}
\tag{78}
$$

To avoid costly proof processing during routine auditing, VeRedact-PQ provides two verification levels. In a *normal audit*, the auditor verifies the Phase 3 post-quantum validation attestation

$$
\mathsf{PQSIG.Verify}
\left(
pk_V,
H(RID_i\parallel C_i^{VR}\parallel e_i),
\alpha_i
\right)=1
\tag{79}
$$

together with $H(\pi_i^{PQ})$ committed in the validated request. The complete PQZK proof is therefore not processed during the normal audit path.

For a challenged or forensic *deep audit*, the complete proof is retrieved and independently verified as

$$
\mathsf{PQZK.Verify}
(vk_{\mathrm{PQZK}},x_i,\pi_i^{PQ})=1
\tag{80}
$$

Hence, expensive PQZK verification is incurred only when stronger evidence is explicitly required.

**Step 5: Query-Specific Audit Decision.** After verifying the required evidence, the auditor computes

$$
\mathsf{AuditVerify}
(PP,Q_j^{A},Resp_j^{A})
\rightarrow(ans_j,\beta_j),
\qquad
\beta_j\in{0,1}
\tag{81}
$$

where $ans_j$ is the verified query result and $\beta_j=1$ only when all authentication, freshness, membership, authorization, and state-transition conditions required by $qtype_j$ are satisfied.

Accordingly, routine audit cost is dominated by post-quantum signature verification and hash-based authenticated-data-structure operations, rather than PQZK verification. Query-scoped multiproofs amortize Merkle verification across multiple returned records, shared ABRRR authorization evidence is verified once per batch, and query-adaptive evidence selection avoids unnecessary proof transmission. Deep PQZK verification remains available when required, thereby preserving post-quantum verifiability without imposing its full cost on every audit query.

## Security Analysis

We analyze VeRedact-PQ under the threat model defined in Section III-B. Let $\mathcal{A}$ be a probabilistic quantum-polynomial-time (QPT) adversary. We assume that PQSIG is existentially unforgeable against quantum chosen-message attacks, PQZK satisfies quantum soundness and zero knowledge, PQCH provides collision resistance and threshold-controlled adaptation against quantum adversaries, $H$ is collision resistant with parameters selected for the required post-quantum security level, PRF is quantum-secure, and the authenticated Merkle structures are binding. We further assume that fewer than $t$ members of each redaction committee are compromised and that the underlying permissioned blockchain satisfies its prescribed consensus fault-tolerance condition.

### Post-Quantum Request Authentication and Policy Compliance

**Theorem 1 (Authenticated and Policy-Compliant Admission).** An adversary cannot cause an unauthorized redaction request to obtain a valid Phase 3 validation attestation except with negligible probability.

*Proof:* For a request $R_i$ to reach private policy verification, it must first satisfy

$$
\mathsf{PQSIG.Verify}
(pk_r,H(R_i),\sigma_i^{R})=1
\tag{82}
$$

Because $pk_r$ is bound to the registered requester, an adversary without $sk_r$ that produces a valid signature on a new $R_i$ directly violates the assumed unforgeability of PQSIG.

Possession of a valid requester key alone is insufficient. The authenticated SA-RLI entry binds the request to its current $(I_i,D_i,b,v_b,e_i)$ state, while the applicable policy is committed by

$$
CP_i=H(PID_i\parallel P_i\parallel v_i\parallel e_i)
\tag{83}
$$

Replacing $P_i$, $PID_i$, $v_i$, or $e_i$ while preserving $CP_i$ requires a collision in $H$.

After the public policy conditions are checked, private eligibility requires an accepting PQZK proof

$$
\mathsf{PQZK.Verify}
(vk_{\mathrm{PQZK}},x_i,\pi_i^{PQ})=1
\tag{84}
$$

where

$$
x_i=(TID_i,I_i,D_i,D_i',CP_i,op_i,b,v_b,e_i)
\tag{85}
$$

If the requester does not possess a witness $w_i$ satisfying $\mathcal{R}_{P}(x_i,w_i)=1$, producing an accepting proof contradicts PQZK soundness.

Finally, the Validation and Policy Service issues

$$
\alpha_i=
\mathsf{PQSIG.Sign}
\left(
sk_V,H(RID_i\parallel C_i^{VR}\parallel e_i)
\right)
\tag{86}
$$

only after all preceding checks succeed. Therefore, obtaining a valid attestation for an unauthorized request requires forging PQSIG, breaking PQZK soundness, violating an authenticated state binding, or finding a collision in $H$, each of which occurs only with negligible probability under the stated assumptions. Hence, an unauthorized request cannot obtain a valid Phase 3 attestation except with negligible probability. $\square$

### Threshold Committee Authorization and Redaction Control

**Theorem 2 (Threshold Redaction Security).** If fewer than $t$ members of the active committee $\mathcal{C}_e$ are compromised, they cannot independently authorize and execute a valid redaction except with negligible probability.

*Proof:* Phase 4 accepts an ABRRR batch only if its authorization set satisfies

$$
|\mathcal{A}_e|\geq t,
\qquad
\mathsf{PQSIG.Verify}
(pk_{e,k},H(C_e^B\parallel e),\sigma_{e,k}^{B})=1
\tag{87}
$$

for every counted committee approval. Let the adversary control $c<t$ committee members. It can generate at most $c$ valid signatures using the corresponding compromised keys. Reaching the threshold therefore requires at least one valid signature under an uncompromised committee key. Producing such a signature contradicts PQSIG unforgeability.

Authorization alone also cannot perform the controlled ledger adaptation. Phase 5 requires at least $t$ valid PQCH adaptation shares:

$$
r_b'=
\mathsf{PQCH.Combine}
\left(
\{\delta_{b,k}\}_{k\in\mathcal{T}_b}
\right),
\qquad |\mathcal{T}_b|\geq t
\tag{88}
$$

Since every committee member possesses only its distributed trapdoor share $td_{e,k}$, fewer than $t$ compromised members cannot derive a valid adaptation under the threshold-security assumption of PQCH.

Thus, an adversary controlling fewer than $t$ members must either forge an honest committee member’s PQ signature or violate the threshold security of PQCH. Both events have negligible probability. Therefore, no sub-threshold coalition can independently authorize and execute an accepted redaction. $\square$

### Batch Integrity and Authorization Binding

**Theorem 3 (Batch Non-Substitution).** After an ABRRR batch has been authorized, no request can be inserted, removed, replaced, or transferred between authorized batches without detection except with negligible probability.

*Proof:* Each validated request contributes the authenticated leaf

$$
\eta_i=
H(RID_i\parallel C_i^{VR}\parallel H(\pi_i^{PQ})
\parallel\alpha_i\parallel b\parallel v_b\parallel e_i)
\tag{89}
$$

and all request leaves determine

$$
R_e^{VR}=
\mathsf{Merkle.Root}(\eta_1,\ldots,\eta_m)
\tag{90}
$$

The batch commitment

$$
C_e^B=
H(BID_e\parallel e\parallel m\parallel
R_e^{VR}\parallel ts_e)
\tag{91}
$$

is the object authorized by at least $t$ committee members.

Suppose $\mathcal{A}$ replaces $\eta_i$ by $\eta_i'$. Unless $\eta_i'=\eta_i$, the authenticated Merkle root changes under the binding property of the Merkle construction. The resulting $C_e^{B'}$ therefore differs from $C_e^B$, and the existing committee signatures fail verification. The same argument applies to insertion or removal because $m$ and the Merkle root are both committed.

For individual verification, $PBRP_i^{auth}$ contains the Merkle membership proof connecting $\eta_i$ to the authorized $R_e^{VR}$. Thus, presenting a request that was not in the authorized batch requires forging a valid Merkle path to the same root or finding a collision in $H$. Both contradict the assumed authenticated-data- structure security. Hence, batch manipulation is detectable except with negligible probability. $\square$

### State Freshness and Replay Resistance

**Theorem 4 (State-Bound Authorization).** A request or authorization generated for transaction state $(D_i,v_b,e_i)$ cannot be validly reused after that state or authorization epoch changes.

*Proof:* Phase 3 binds $(D_i,b,v_b,e_i)$ to the public PQZK statement, validated-request commitment, and validation attestation. Phase 4 further includes these values in $\eta_i$, which is committed by $R_e^{VR}$ and $C_e^B$.

Before authorization and again immediately before execution, the system verifies

$$
(D_i,v_b,e_i)
\stackrel{?}{=}
(D_i^{cur},v_b^{cur},e^{cur})
\tag{92}
$$

After successful redaction,

$$
v_b'=v_b+1
\tag{93}
$$

Therefore, previously generated evidence containing $v_b$ fails the freshness test against $v_b'$. Similarly, evidence generated in epoch $e_i$ fails once $e^{cur}\neq e_i$.

An adversary cannot alter the version or epoch inside existing evidence because doing so changes the associated hash commitments, PQZK statement, Merkle leaf, and committee-signed batch commitment. Successful alteration would therefore require a hash collision, signature forgery, or new valid authorization. Consequently, stale authorization and replayed requests cannot be accepted except with negligible probability. $\square$

### Controlled Redaction and Ledger Consistency

**Theorem 5 (Policy-Bound Redaction Integrity).** An accepted VeRedact-PQ redaction modifies only the authorized redactable content state while preserving the immutable transaction-policy binding and PQCH commitment.

*Proof:* The Redaction-Aware Dual Commitment (RADC) separates the transaction state into

$$
I_i=
H(TID_i\parallel ID_{DO_i}\parallel DT_i
\parallel PID_i\parallel ts_i\parallel Tag_i)
\tag{94}
$$

$$
D_i=H(m_i)
\tag{95}
$$

For an authorized redaction $m_i\rightarrow m_i'$, Phase 5 requires

$$
I_i'=I_i
\tag{96}
$$

$$
D_i'=H(m_i')
\tag{97}
$$

Hence, changing the transaction identity, owner, data type, policy, timestamp, or transaction tag while preserving $I_i$ requires a collision in $H$.

All authorized changes affecting transaction batch $b$ are committed to the updated Merkle root $MR_b'$. Ledger continuity is accepted only when

$$
\begin{split}
\mathsf{PQCH.Hash}(pk_{\mathrm{CH}},MR_b,r_b)
=\\
\mathsf{PQCH.Hash}(pk_{\mathrm{CH}},MR_b',r_b')
=
CH_b

\end{split}
\tag{98}
$$

For $MR_b'\neq MR_b$, generating valid $r_b'$ without the required threshold adaptation violates the security of PQCH. By Theorem 2, fewer than $t$ compromised committee members cannot generate such an adaptation.

Therefore, an accepted transition preserves $I_i$ and $CH_b$ while changing only the committee-authorized content state $D_i$. Any unauthorized modification must break either the RADC hash binding, Merkle authentication, threshold PQCH security, or committee authorization, all of which succeed only with negligible probability. $\square$

### End-to-End Redaction Accountability

**Theorem 6 (Verifiable Redaction Accountability).** Every successfully executed redaction is cryptographically traceable to its independently validated request, applicable policy and state, committee-authorized ABRRR batch, and resulting ledger transition.

*Proof:* For every executed request, VeRedact-PQ constructs

$$
\begin{split}
PBRP_i = (PBRP_i^{auth},I_i,D_i,D_i',
b,v_b,v_b',\\MR_b,MR_b',CH_b,e,BID_e)
\end{split}
\tag{99}
$$

By Theorem 1, the validated request represented inside $PBRP_i^{auth}$ has passed requester authentication and policy verification. By Theorem 3, its membership proof binds it to the specific $R_e^{VR}$ and committee-authorized $C_e^B$. By Theorem 4, the authorization is bound to the applicable transaction version and epoch. Finally, by Theorem 5, $(MR_b,MR_b',CH_b)$ binds the evidence to the controlled state transition actually executed.

The redaction record additionally contains

$$
H(PBRP_i)
\tag{100}
$$

which is authenticated by RAI and its blockchain-anchored checkpoint. Replacing any component of $PBRP_i$ while retaining the same digest requires a collision in $H$. Replacing the authenticated audit entry requires violating the Merkle binding or anchored checkpoint.

Hence, a valid redaction record establishes a continuous cryptographic chain

$$
\begin{split}
&\text{authenticated request}
\Rightarrow \text{policy validation}
\Rightarrow \text{batch authorization}\\
&\Rightarrow \text{authorized state transition}
\Rightarrow \text{authenticated audit record}.
\end{split}
\tag{101}
$$

Breaking this chain requires violating at least one of the stated cryptographic assumptions. Therefore, accepted redactions remain independently accountable except with negligible probability. $\square$

### Privacy-Preserving and Fresh Auditing

**Theorem 7 (Audit Privacy and Integrity).** Under PQZK zero knowledge, PRF security, hash collision resistance, PQSIG unforgeability, and Merkle binding, an authorized auditor can verify the requested redaction properties without learning the private policy witness or requiring disclosure of the original transaction content, while modification or substitution of returned authenticated evidence is detectable.

*Proof:* The private credentials and authorization attributes used in Phase 3 occur only in witness $w_i$. PQZK zero knowledge guarantees that $\pi_i^{PQ}$ reveals no information about $w_i$ beyond the truth of

$$
\mathcal{R}_{P}(x_i,w_i)=1
\tag{102}
$$

Routine auditing does not require $w_i$ and normally does not process $\pi_i^{PQ}$; instead, it verifies the PQ-signed validation attestation $\alpha_i$ and the committed $H(\pi_i^{PQ})$. Full proof verification is performed only when a challenged or forensic audit requires it.

RAI further replaces direct transaction lookup identifiers with

$$
\tau_i^A=\mathsf{PRF}_{K_A}(TID_i)
\tag{103}
$$

and stores only compact metadata and $H(PBRP_i)$ in the authenticated index. Under PRF security, a party without $K_A$ cannot invert $\tau_i^A$ to recover $TID_i$ better than allowed by the underlying identifier distribution and auxiliary information.

For integrity and freshness, RAI entries are authenticated under $R_{\mathrm{RAI}}$, which is bound to the epoch checkpoint

$$
CP_e^A=
H(e\parallel R_{\mathrm{RAI}}\parallel v_A\parallel ts_e)
\tag{104}
$$

An audit response is PQ-signed and contains a query-scoped Merkle multiproof. Modifying a returned entry requires either constructing a false path to $R_{\mathrm{RAI}}$ or finding a hash collision. Substituting another audit response requires forging the audit service’s PQ signature. Substituting stale state is detected by the epoch, version, timestamp, and blockchain-anchored checkpoint.

Accordingly, the auditor can verify the authenticated evidence and its freshness without disclosure of the private authorization witness or original transaction content. The protocol intentionally reveals query-authorized metadata such as batch identifiers, epochs, versions, and timestamps; these values are therefore outside the privacy claim. $\square$

**Remark on Query Completeness:** A Merkle multiproof establishes membership and integrity of the returned RAI entries but, by itself, does not prove that every entry satisfying an arbitrary semantic predicate has been returned. Therefore, VeRedact-PQ claims authenticated integrity and freshness for the resolved query result. Queries requiring cryptographic result-set completeness additionally require authenticated coverage, range, or non-membership evidence appropriate to the corresponding RAI query structure.

### Post-Quantum Security and Blockchain Security Boundary

**Theorem 8 (Post-Quantum Redaction Security).** Under the stated PQ assumptions and provided that the committee and permissioned-consensus thresholds are not violated, a QPT adversary cannot cause an unauthorized redaction to be accepted by VeRedact-PQ except with negligible probability, even when the underlying permissioned blockchain uses classical platform credentials.

*Proof:* Consider a QPT adversary attempting to create an accepted unauthorized redaction. The VeRedact-PQ acceptance path requires all of the following:

$$
\begin{split}
&\mathsf{PQ\ requester\ authentication}\\
&\Rightarrow
\mathsf{PQZK\ policy\ validation}\\
&\Rightarrow
t\text{-of-}n\ \mathsf{PQ\ committee\ authorization}\\
&\Rightarrow
\mathsf{threshold\ PQCH\ adaptation}\\
&\Rightarrow
\mathsf{authenticated\ redaction\ evidence}.
\end{split}
\tag{105}
$$

By Theorem 1, bypassing the first two conditions requires breaking PQSIG or PQZK. By Theorem 2, producing committee authorization with fewer than $t$ compromised members requires forging an honest PQ signature, while executing the corresponding state adaptation requires violating threshold PQCH security. Theorems 3–6 prevent a valid request or authorization from being transferred to another batch, state, epoch, or redaction transition. These primitives are assumed secure against QPT adversaries.

Now consider compromise of a classical credential belonging to the underlying Permissioned Blockchain Network (PBN). Such a credential may permit the adversary to authenticate to the platform or submit a native blockchain transaction, depending on the platform’s access policy. It does not, however, provide $\sigma_i^R$, $\alpha_i$, the required $t$ committee PQ approvals, or $t$ valid PQCH adaptation shares. Therefore, possession of a classical PBN credential alone cannot satisfy Eq. (105) and cannot produce an accepted VeRedact-PQ redaction.

This establishes a *post-quantum redaction-security boundary*: the security-critical authentication, private policy verification, committee authorization, controlled adaptation, and audit evidence of VeRedact-PQ do not rely solely on the native classical authentication of the PBN.

This result does not imply that the underlying PBN is itself fully post-quantum secure. If a quantum adversary compromises enough native identities to violate the PBN consensus fault-tolerance assumption, ledger integrity or availability may fail independently of the redaction protocol. Such a violation is explicitly outside the threat model. Full post-quantum security of the blockchain substrate would additionally require PQ-secure membership, node authentication, endorsement, transport credentials where applicable, and consensus authentication. Subject to the stated PBN assumption, however, breaking the VeRedact-PQ redaction path requires breaking at least one of its PQ cryptographic assumptions or the committee threshold. Therefore, the probability of an unauthorized accepted redaction is negligible. $\square$

## Evaluation

### Cost Analysis

### Communication Cost Analysis

### Performance Analysis

This subsection describes the implementation, parameter configuration, and experimental design used to evaluate VeRedact-PQ. The evaluation examines five aspects of the redaction lifecycle: redaction latency and throughput, transaction authorization latency, audit efficiency, audit verification time, and on-chain gas consumption.

#### Experimental Setup

**Testbed.** All experiments are conducted on **[CPU model, number of cores, clock frequency]** with **[RAM]** running **[OS and version]**. Each consortium organization, committee member, the VPS, and the audit service are deployed as separate containerized processes connected through a local network. Unless otherwise stated, cryptographic operations are executed on a single core so that per-operation costs are not affected by parallelism, whereas the end-to-end experiments allow parallel PQCH share generation and parallel processing of distinct transaction batches as described in Algorithm 1.

**Blockchain Platform.** The Permissioned Blockchain Network (PBN) is instantiated with Hyperledger Besu **[version]** using the QBFT consensus protocol with $7$ validator nodes, one per consortium organization, and a block period of $2$ s. Redaction-relevant on-chain state, including policy commitments $C_{P_j}$, committee configurations $(e,\mathcal{C}_e,t)$, batch checkpoints $A_b$ and $A_b'$, ABRRR authorization records, and audit checkpoints $CP_e^{A}$, is managed by Solidity smart contracts. Because on-chain verification of lattice-based signatures and proofs is prohibitively expensive in the EVM, these objects are verified off-chain by the corresponding entities, and only their digests and roots are anchored on-chain.

**Cryptographic Instantiation.** All primitives are selected for NIST post-quantum security level 3. PQSIG is instantiated with ML-DSA-65 (FIPS 204), $H$ with SHA3-256, and PRF with HMAC-SHA3-256. PQCH is instantiated with a lattice-based (SIS-based) chameleon hash supporting $t$-of-$n$ distributed trapdoor shares. PQZK is instantiated with a hash-based transparent STARK proof system, consistent with the trapdoor-free setup assumed in Phase 1. Merkle trees, BIMC, SA-RLI, and RAI use SHA3-256 as the node hash. The prototype is implemented in **[language and libraries]**.

**Workload.** Transactions are synthetic enterprise records with a default payload size of $1$ KB and are committed in transaction batches of $N=1024$ leaves. The ledger is pre-populated with between $10^{4}$ and $10^{6}$ committed transactions. Redaction requests are generated according to a Poisson process with arrival rate $\lambda$, and targets are selected either uniformly at random or according to a Zipf distribution with skew $s\in\{0.5,0.99\}$. The target distribution controls redaction locality, i.e., the number $k$ of redactions that fall into the same transaction batch and can therefore be coalesced by BIMC. For experiments with invalid traffic, a fraction $\rho$ of requests is malformed, replayed, targets a nonexistent transaction, or carries an invalid signature or PQZK proof.

**Parameters.** Table II summarizes the evaluated parameters. When one parameter is varied, the remaining parameters are fixed at their default values.

**Table II.** Evaluation Parameters (Default Values in Bold)

| **Parameter** | **Values** |
|:---|:---|
| Security level | NIST level 3 |
| Committee size / threshold $(n,t)$ | $(4,3)$, $\mathbf{(7,5)}$, $(10,7)$, $(13,9)$, $(16,11)$ |
| Request arrival rate $\lambda$ (req/s) | $50$, $100$, $\mathbf{200}$, $500$, $1000$ |
| ABRRR bounds $(B_{\min},B_{\max})$ | $(1,\mathbf{256})$ |
| Fixed batch size (for comparison) | $1$, $16$, $32$, $64$, $128$, $256$ |
| Maximum waiting time $T_{\max}$ (ms) | $50$, $\mathbf{100}$, $200$, $500$ |
| Transaction batch size $N$ | $\mathbf{1024}$ |
| Ledger size (transactions) | $10^{4}$, $\mathbf{10^{5}}$, $10^{6}$ |
| Redactions per affected batch $k$ | $1$, $2$, $4$, $8$, $\mathbf{16}$, $32$ |
| Target distribution | Uniform, **Zipf** ($s=0.99$) |
| Invalid request ratio $\rho$ | $\mathbf{0}$, $10\%$, $30\%$, $50\%$ |
| SA-RLI shards $S$ | $1$, $4$, $\mathbf{16}$, $64$ |
| RAI shards $S_A$ | $1$, $4$, $\mathbf{16}$, $64$ |
| RAI size (redaction records) | $10^{3}$, $10^{4}$, $\mathbf{10^{5}}$, $10^{6}$ |
| Query result size $|\mathcal{R}_{Q_j}|$ | $1$, $10$, $\mathbf{50}$, $100$, $500$ |
| Audit level | **Normal**, Deep |

**Compared Schemes.** VeRedact-PQ is compared with representative schemes from Table I: the decentralized chameleon-hash scheme of Jia *et al.* [1], the threshold redaction scheme of Liu *et al.* [27], the quantum-resistant scheme of Wang *et al.* [17], and the auditable schemes VRBC [13] and Xue *et al.* [33]. Each scheme is evaluated on the same testbed and workload for the operations it supports. To isolate the contribution of each mechanism, the following ablated variants of VeRedact-PQ are also evaluated:

- **VeRedact-PQ-NB**: no batching; every request is authorized, redacted, and anchored individually ($B=1$).

- **VeRedact-PQ-FB**: fixed-size batching instead of ABRRR.

- **VeRedact-PQ-NC**: ABRRR without BIMC coalescing; each redaction performs its own Merkle update and PQCH adaptation.

- **VeRedact-PQ-NM**: auditing with independent Merkle proofs and per-record authorization evidence instead of query-scoped multiproofs and shared batch evidence.

**Measurement Methodology.** Each configuration is executed $30$ times after $5$ warm-up runs. Latency is reported as the mean with $95\%$ confidence interval, together with the median and the $95$th and $99$th percentiles for end-to-end experiments. Throughput measurements run for $300$ s at a steady arrival rate after a $60$ s warm-up period.

#### Experiment 1: Redaction Latency and Throughput

This experiment evaluates the end-to-end efficiency of the complete redaction workflow. The redaction latency of request $R_i$ is measured from request submission to the on-chain commitment of the updated checkpoint $A_b'$:

$$
T_i^{red}=T_i^{val}+T_i^{wait}+T_i^{auth}+T_i^{exec}+T_i^{cons}
\tag{106}
$$

where $T_i^{val}$ is the Phase 3 validation time, $T_i^{wait}$ is the ABRRR queuing time, $T_i^{auth}$ is the Phase 4 committee authorization time, $T_i^{exec}$ is the Phase 5 BIMC update and distributed PQCH adaptation time, and $T_i^{cons}$ is the time required to commit the updated checkpoint through consensus. Throughput is defined as

$$
TP=\frac{N_{red}}{T_{obs}}
\tag{107}
$$

where $N_{red}$ is the number of redactions committed during the observation window $T_{obs}$. The maximum sustainable throughput is the largest $\lambda$ for which the request queue remains bounded and the $95$th-percentile latency does not exceed $2T_{\max}$ plus one block period.

The experiment consists of four configurations: (i) varying $\lambda$ from $50$ to $1000$ req/s for VeRedact-PQ, VeRedact-PQ-NB, VeRedact-PQ-FB, and the compared schemes; (ii) varying the redaction locality $k$ from $1$ to $32$ to quantify the effect of BIMC coalescing against VeRedact-PQ-NC; (iii) varying the committee size $(n,t)$ to measure the cost of distributed PQCH adaptation; and (iv) varying the ledger size from $10^{4}$ to $10^{6}$ to evaluate target resolution through SA-RLI. The latency breakdown of Eq. (106) is reported for each configuration.

#### Experiment 2: Transaction Authorization Latency

This experiment isolates the cost of admitting and authorizing a redaction request, i.e., Phases 3 and 4. For an ABRRR batch of $m$ requests, the amortized authorization latency per request is

$$
\bar{T}^{auth}=
\frac{1}{m}\sum_{i=1}^{m}T_i^{val}
+\frac{T^{att}(m)+T^{root}(m)+T^{sig}(t)}{m}
\tag{108}
$$

where $T^{att}(m)$ is the time to verify the $m$ validation attestations $\alpha_i$ and state freshness, $T^{root}(m)$ is the time to construct $R_e^{VR}$ and $C_e^{B}$, and $T^{sig}(t)$ is the time to collect and verify $t$ committee signatures $\sigma_{e,k}^{B}$.

Three configurations are evaluated. First, the per-stage cost of Phase 3, namely admission and SA-RLI lookup, requester signature verification, public policy validation, PQZK verification, and attestation generation, is measured for a single request. Second, the batch size $m$ and committee size $(n,t)$ are varied to measure the amortization of committee authorization relative to VeRedact-PQ-NB, which requires $t$ committee signatures per request. Third, the invalid request ratio $\rho$ is varied from $0$ to $50\%$ to evaluate the staged rejection strategy, reporting the average time spent on rejected requests and the number of PQZK verifications avoided.

#### Experiment 3: Audit Efficiency

This experiment evaluates the cost of maintaining the Redaction Audit Index and answering audit queries at the audit service. The following metrics are measured: (i) RAI insertion time per redaction record and per ABRRR batch; (ii) epoch checkpoint generation time for $CP_e^{A}$; (iii) query resolution time for $\mathcal{R}_{Q_j}$; (iv) evidence generation time for $MP_{Q_j}^{A}$ and $\Pi_{Q_j}$, including response signing; and (v) the audit response size $|Resp_j^{A}|$ in bytes.

The RAI size is varied from $10^{3}$ to $10^{6}$ records, the number of RAI shards $S_A$ from $1$ to $64$, and the query result size $|\mathcal{R}_{Q_j}|$ from $1$ to $500$. Each query type defined in Phase 6, namely integrity, history, authorization, policy compliance, scope, freshness, batch membership, and epoch/time queries, is evaluated separately to measure the effect of query-adaptive evidence selection. VeRedact-PQ is compared with VeRedact-PQ-NM and the auditable schemes [13, 33].

#### Experiment 4: Verification Time

This experiment evaluates the auditor-side cost of verifying an audit response, i.e., the $\mathsf{AuditVerify}$ algorithm of Phase 6. The verification time for a response is decomposed as

$$
T^{ver}_j=
T^{sig}_{resp}+T^{mp}(|\mathcal{R}_{Q_j}|)
+|\Omega_{Q_j}^{B}|\cdot T^{batch}
+\sum_{E_i^{A}\in\mathcal{R}_{Q_j}}T_i^{rec}
\tag{109}
$$

where $T^{sig}_{resp}$ is the verification time of $\sigma_{Resp}^{A}$ and the anchored checkpoint, $T^{mp}$ is the multiproof verification time, $T^{batch}$ is the verification time of the shared ABRRR evidence per distinct batch, and $T_i^{rec}$ is the per-record verification time of the PBRP components required by $qtype_j$.

The experiment compares normal audits, which verify $\alpha_i$ and $H(\pi_i^{PQ})$, with deep audits, which additionally execute $\mathsf{PQZK.Verify}$ for every returned record. The query result size $|\mathcal{R}_{Q_j}|$ is varied from $1$ to $500$, and the number of distinct ABRRR batches $|\Omega_{Q_j}^{B}|$ covered by a fixed result of $100$ records is varied from $1$ to $100$ to quantify the benefit of verifying shared batch evidence once. The verification time of a single redaction is additionally compared with that of the compared schemes.

#### Experiment 5: Blockchain Gas Consumption

This experiment measures the on-chain cost of VeRedact-PQ in EVM gas. Gas is measured from transaction receipts for the following contract operations: policy registration $(PID_j,C_{P_j},v_j,e)$, committee configuration $(e,\mathcal{C}_e,t)$, transaction-batch checkpoint anchoring $A_b$, ABRRR authorization anchoring, redaction checkpoint update $A_b'$, and audit checkpoint anchoring $CP_e^{A}$. The amortized gas per redaction is defined as

$$
\bar{G}^{red}=
\frac{G^{auth}+\sum_{b\in\Omega_e}G_b^{upd}}{m}
\tag{110}
$$

where $G^{auth}$ is the gas used to anchor the authorization of an ABRRR batch of $m$ requests and $G_b^{upd}$ is the gas used to update the checkpoint of affected transaction batch $b$.

The batch size $m$ is varied from $1$ to $256$ and the redaction locality $k$ from $1$ to $32$ to evaluate the amortization achieved by ABRRR and BIMC, and the results are compared with VeRedact-PQ-NB and VeRedact-PQ-NC. To justify anchoring digests rather than full post-quantum evidence, the gas of storing only $H(\cdot)$ digests is also compared with that of storing complete ML-DSA-65 signatures and committee approval sets on-chain.

## Acknowledgement

This research has been supported by the Thammasat University Research Unit in Cyber Security.

## References

[1] M. Jia, J. Chen, K. He, R. Du, L. Zheng, M. Lai, D. Wang, and F. Liu, “Redactable Blockchain from Decentralized Chameleon Hash Functions,” *IEEE Trans. Inf. Forensics Security*, vol. 17, pp. 2771–2783, 2022, doi: 10.1109/TIFS.2022.3192716.

[2] K. Huang, X. Zhang, Y. Mu, X. Wang, G. Yang, X. Du, F. Rezaeibagha, Q. Xia, and M. Guizani, “Building Redactable Consortium Blockchain for Industrial Internet-of-Things,” *IEEE Trans. Ind. Informat.*, vol. 15, no. 6, pp. 3670–3679, Jun. 2019, doi: 10.1109/TII.2019.2901011.

[3] W. Wang, L. Wang, J. Duan, X. Tong, and H. Peng, “Redactable Blockchain Based on Decentralized Trapdoor Verifiable Delay Functions,” *IEEE Trans. Inf. Forensics Security*, vol. 19, pp. 7492–7507, 2024, doi: 10.1109/TIFS.2024.3431917.

[4] H. Guo, W. Gan, M. Zhao, C. Zhang, T. Wu, L. Zhu, and J. Xue, “PriChain: Efficient Privacy-Preserving Fine-Grained Redactable Blockchains in Decentralized Settings,” *Chinese Journal of Electronics*, vol. 34, no. 1, pp. 82–97, 2025, doi: 10.23919/cje.2023.00.305.

[5] D. Zhang, J. Le, X. Lei, T. Xiang, and X. Liao, “Secure Redactable Blockchain With Dynamic Support,” *IEEE Trans. Dependable Secure Comput.*, vol. 21, no. 2, pp. 717–731, 2024, doi: 10.1109/TDSC.2023.3261343.

[6] X. Wu, X. Du, Q. Yang, N. Wang, and W. Wang, “Redactable consortium blockchain based on verifiable distributed chameleon hash functions,” *J. Parallel Distrib. Comput.*, vol. 183, Art. no. 104777, 2024, doi: 10.1016/j.jpdc.2023.104777.

[7] S. Aguincha, E. Nunes, S. Eisa, and M. L. Pardal, “ChainGuards: Verification of Sensed Data using Permissioned Blockchain Technology,” arXiv preprint arXiv:2603.20769, 2026.

[8] D. Derler, K. Samelin, D. Slamanig, and C. Striecks, “Fine-Grained and Controlled Rewriting in Blockchains: Chameleon-Hashing Gone Attribute-Based,” in *Proc. 26th Annu. Netw. Distrib. Syst. Security Symp. (NDSS)*, 2019, doi: 10.14722/ndss.2019.23066.

[9] G. Ateniese, B. Magri, D. Venturi, and E. R. Andrade, “Redactable Blockchain – or – Rewriting History in Bitcoin and Friends,” in *Proc. 2nd IEEE Eur. Symp. Security Privacy (EuroS&P)*, Paris, France, pp. 111–126, 2017, doi: 10.1109/EuroSP.2017.37.

[10] C. Peng, H. Xu, and P. Li, “Redactable Blockchain Using Lattice-based Chameleon Hash Function,” in *Proc. 2022 Int. Conf. Blockchain Technology Information Security (ICBCTIS)*, pp. 94–98, 2022, doi: 10.1109/ICBCTIS55569.2022.00032.

[11] C. Wu, L. Ke, and Y. Du, “Quantum resistant key-exposure free chameleon hash and applications in redactable blockchain,” *Information Sciences*, vol. 548, pp. 438–449, 2021, doi: 10.1016/j.ins.2020.10.008.

[12] K. Y. Chan, L. Chen, Y. Tian, and T. H. Yuen, “Reconstructing Chameleon Hash: Full Security and the Multi-Party Setting,” in *Proc. 19th ACM Asia Conf. Computer and Communications Security (AsiaCCS)*, pp. 1076–1091, 2024, doi: 10.1145/3634737.3656291.

[13] G. Tian, J. Wei, M. Kutylowski, W. Susilo, X. Huang, and X. Chen, “VRBC: A Verifiable Redactable Blockchain with Efficient Query and Integrity Auditing,” *IEEE Trans. Comput.*, vol. 72, no. 7, pp. 1928–1942, Jul. 2023, doi: 10.1109/TC.2022.3230900.

[14] K. Huang, X. Zhang, Y. Mu, F. Rezaeibagha, and X. Du, “Scalable and redactable blockchain with update and anonymity,” *Information Sciences*, vol. 546, pp. 25–41, 2021, doi: 10.1016/j.ins.2020.07.016.

[15] Y. Dong, Y. Li, Y. Cheng, and D. Yu, “Redactable consortium blockchain with access control: Leveraging chameleon hash and multi-authority attribute-based encryption,” *High-Confidence Computing*, vol. 4, no. 1, Art. no. 100168, 2024, doi: 10.1016/j.hcc.2023.100168.

[16] Y. Zhang, Z. Ma, S. Luo, and P. Duan, “Dynamic Trust-Based Redactable Blockchain Supporting Update and Traceability,” *IEEE Trans. Inf. Forensics Security*, vol. 19, pp. 821–834, 2024, doi: 10.1109/TIFS.2023.3326379.

[17] X. Wang, Y. Chen, X. Zhu, C. Li, and K. Fang, “A Redactable Blockchain Scheme Supporting Quantum-Resistance and Trapdoor Updates,” *Applied Sciences*, vol. 14, no. 2, Art. no. 832, 2024, doi: 10.3390/app14020832.

[18] J. B. Klamti and M. A. Hasan, “Revocable policy-based chameleon hash using lattices,” *Journal of Mathematical Cryptology*, vol. 18, no. 1, Art. no. 20230012, pp. 152–182, 2024, doi: 10.1515/jmc-2023-0012.

[19] X. Huang, Y. Wang, Y. Ding, Q. Wu, C. Yang, and H. Liang, “Dynamically redactable Blockchain based on decentralized Chameleon hash,” *Digital Communications and Networks*, vol. 11, no. 3, pp. 757–767, 2025, doi: 10.1016/j.dcan.2024.10.013.

[20] M. Miao, X. Yang, J. Wei, G. Tian, and W. Susilo, “A Verifiable and Redactable Blockchain with Lightweight Storage and Permission Supervision,” *Information*, vol. 17, no. 2, Art. no. 176, 2026, doi: 10.3390/info17020176.

[21] S. Fugkeaw, S. Sungchai, S. Nakprame, and P. Sreekongpan, “Enabling Secure and Scalable GDPR-Compliant Blockchain-Based e-KYC With Efficient Redaction,” *IEEE Access*, vol. 13, pp. 136834–136853, 2025, doi: 10.1109/ACCESS.2025.3594656.

[22] C. G. Harris, "A Redactable Blockchain Architecture for Regulatory Compliance," 2025 IEEE International Conference on Blockchain (Blockchain), Zhengzhou, China, 2025, pp. 1-6, doi: 10.1109/Blockchain67634.2025.00010.

[23] Z. Wu, L. Wang, X. Zhang and X. Feng, "EMT: Extended Merkle Tree Structure for Inserted Data Redaction in Permissioned Blockchain," in IEEE Transactions on Network Science and Engineering, vol. 12, no. 4, pp. 3025-3038, July-Aug. 2025, doi: 10.1109/TNSE.2025.3555979.

[24] J. W. Heo, G. Ramachandran and R. Jurdak, "Decentralised Redactable Blockchain: A Privacy-Preserving Approach to Addressing Identity Tracing Challenges," 2024 IEEE International Conference on Blockchain and Cryptocurrency (ICBC), Dublin, Ireland, 2024, pp. 215-219, doi: 10.1109/ICBC59979.2024.10634438.

[25] T. Sengupta, S. Chakraborty, and S. Sural, “ReAcct: Redaction control for interoperable blockchains,” in *Proc. 7th Conf. Blockchain Research Appl. Innovative Networks Services (BRAINS)*, Zurich, Switzerland, 2025, pp. 1–10, doi: 10.1109/BRAINS67003.2025.11302947.

[26] L. Yin, J. Shi, B. Xie and Y. Liu, "Rchain: A Universal and Efficient Redactable Blockchain Scheme," 2025 IEEE International Conference on Blockchain (Blockchain), Zhengzhou, China, 2025, pp. 235-240, doi: 10.1109/Blockchain67634.2025.00038.

[27] Z. Liu, B. Zhou and Y. Zhao, "Enhancing Redactable Blockchain With Robust and Efficient Threshold Redaction," in IEEE Transactions on Dependable and Secure Computing, vol. 23, no. 2, pp. 3238-3251, March-April 2026, doi: 10.1109/TDSC.2025.3634512.

[28] F. Wang, R. Dong, J. Cui, Q. Zhang and H. Zhong, "Blockchain-Based Anonymous and Accountable Data Redaction for the Industrial Internet of Things," in IEEE Transactions on Cloud Computing, doi: 10.1109/TCC.2026.3725253.

[29] S. Biswas, S. Chakraborty, and R. S. Chakraborty, “Redacting without regret: A dual-layer framework for policy-compliant blockchains,” in *Proc. 7th Conf. Blockchain Research Appl. Innovative Networks Services (BRAINS)*, Zurich, Switzerland, 2025, pp. 1–9, doi: 10.1109/BRAINS67003.2025.11302930.

[30] C. Li, Q. Shen and Z. Wu, "Redactable Blockchain From Decentralized Chameleon Hash Functions, Revisited," in IEEE Transactions on Computers, vol. 74, no. 6, pp. 1911-1920, June 2025, doi: 10.1109/TC.2025.3544878.

[31] Z. Yuqi, "Policy-Hiding Chameleon Hash with Traceability for Redactable Blockchains," 2025 22nd International Computer Conference on Wavelet Active Media Technology and Information Processing (ICCWAMTIP), Chengdu, China, 2025, pp. 1-4, doi: 10.1109/ICCWAMTIP68645.2025.11352637.

[32] S. Hu, M. Li, J. Weng, J. -N. Liu, J. Weng and Z. Li, "IvyRedaction: Enabling Atomic, Consistent and Accountable Cross-Chain Rewriting," in IEEE Transactions on Dependable and Secure Computing, vol. 21, no. 4, pp. 3883-3900, July-Aug. 2024, doi: 10.1109/TDSC.2023.3339675.

[33] L. Xue, H. Huang, F. Xiao, Q. Li and W. Wang, "A Controllable, Publicly Auditable, and Redactable Blockchain With a Main–Auxiliary Architecture," in IEEE Transactions on Dependable and Secure Computing, vol. 23, no. 2, pp. 1847-1864, March-April 2026, doi: 10.1109/TDSC.2025.3620854.

[34] J. Xue et al., "Attribute-Based Policy-Hiding Redactable Blockchain With Authorizable Verification for Energy Internet," in IEEE Internet of Things Journal, vol. 12, no. 15, pp. 29570-29583, 1 Aug.1, 2025, doi: 10.1109/JIOT.2025.3569699.

[35] K. Huang, X. Li, F. Rezaeibagha, L. Zhang and X. Zhang, "Time Updatable Policy-Based Chameleon Hash for Traceable and Accountable Redactable Blockchain," in IEEE Transactions on Information Forensics and Security, vol. 21, pp. 1470-1483, 2026, doi: 10.1109/TIFS.2026.3655919.

[36] J. Duan, W. Wang, L. Wang and L. Gu, "Controlled Redactable Blockchain Based on T-Times Chameleon Hash and Signature," in IEEE Transactions on Information Forensics and Security, vol. 19, pp. 7560-7572, 2024, doi: 10.1109/TIFS.2024.3436925.

[37] W. -C. Kuo, D. -R. Lin and S. -X. Chen, "Identity-Based Chameleon Hashing from the SIS Assumption in a Central Authority Model," 2025 IEEE Conference on Dependable and Secure Computing (DSC), Taipei, Taiwan, 2025, pp. 1-6, doi: 10.1109/DSC65356.2025.11260874.

[38] M. Shirmohammadi, A. Islam and H. Karimipour, "An Intent-Based Networking Framework for Secure and Privacy-Compliant Machine Unlearning Using Meta-Learning and Redactable Blockchain," in IEEE Internet of Things Journal, vol. 13, no. 9, pp. 18167-18181, 1 May1, 2026, doi: 10.1109/JIOT.2025.3638966.
