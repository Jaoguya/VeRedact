// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @title VeRedact-PQ on-chain anchoring (Exp. 5)
/// @notice Stores digests only. PQ signatures (ML-DSA-65) are verified off-chain by the validator
///         nodes before anchoring (paper, Sec. Experimental Setup) and are passed as calldata so
///         their size is reflected in gas; only keccak256(sig) is kept on-chain.
contract VeRedactRegistry {
    struct Checkpoint {          // A_b
        bytes32 chDigest;        // H(CH_b)   (PQCH value is larger than one word)
        bytes32 mr;              // MR_b
        bytes32 rDigest;         // H(r_b)
        bytes32 rRli;            // R_RLI
        uint64 vRli;             // v_RLI
        uint64 epoch;            // e
        uint64 vb;               // v_b
        uint64 ts;               // ts_b
        bytes32 sigDigest;       // H(sigma_b)
    }

    address public immutable ordering;           // PBN ordering service / validator gateway
    mapping(bytes32 => bytes32) public policy;    // PID -> H(C_P, v, e_P)
    mapping(uint64 => bytes32) public committee;  // e -> H(C_e, n, t)
    mapping(uint256 => Checkpoint) public checkpoints;
    mapping(bytes32 => bytes32) public authorizations; // BID -> H(Auth_e^B)
    mapping(uint64 => bytes32) public raiCheckpoints;  // e -> CP_e^A

    event PolicyRegistered(bytes32 indexed pid, bytes32 cP, uint64 v, uint64 eP);
    event CommitteeRegistered(uint64 indexed epoch, bytes32 membersRoot, uint16 n, uint16 t);
    event CheckpointAnchored(uint256 indexed b, uint64 vb, bytes32 mr);
    event RedactionFinalized(bytes32 indexed bid, uint256 transitions);
    event RaiCheckpoint(uint64 indexed epoch, bytes32 cp);

    modifier onlyOrdering() {
        require(msg.sender == ordering, "not ordering service");
        _;
    }

    constructor() {
        ordering = msg.sender;
    }

    // ---------------- Phase 1 ----------------
    function registerPolicy(bytes32 pid, bytes32 cP, uint64 v, uint64 eP, bytes calldata pqSig) external onlyOrdering {
        policy[pid] = keccak256(abi.encode(cP, v, eP, keccak256(pqSig)));
        emit PolicyRegistered(pid, cP, v, eP);
    }

    function registerCommittee(uint64 epoch, bytes32 membersRoot, uint16 n, uint16 t, bytes calldata pqSig)
        external onlyOrdering
    {
        require(t > 0 && t <= n, "bad threshold");
        committee[epoch] = keccak256(abi.encode(membersRoot, n, t, keccak256(pqSig)));
        emit CommitteeRegistered(epoch, membersRoot, n, t);
    }

    // ---------------- Phase 2 ----------------
    function anchorCheckpoint(uint256 b, Checkpoint calldata cp, bytes calldata sig) external onlyOrdering {
        require(checkpoints[b].ts == 0, "exists");
        _store(b, cp, sig);
    }

    // ---------------- Phase 4 ----------------
    function anchorAuthorization(bytes32 bid, bytes32 authDigest) external onlyOrdering {
        authorizations[bid] = authDigest;
    }

    // ---------------- Phase 5: atomic finalization of all affected batches ----------------
    function finalizeRedaction(
        bytes32 bid,
        uint256[] calldata bs,
        Checkpoint[] calldata cps,
        bytes[] calldata sigs
    ) external onlyOrdering {
        require(bs.length == cps.length && cps.length == sigs.length, "length");
        require(authorizations[bid] != bytes32(0), "unauthorized batch");
        for (uint256 i = 0; i < bs.length; i++) {
            Checkpoint storage prev = checkpoints[bs[i]];
            require(prev.ts != 0 && cps[i].vb == prev.vb + 1, "stale version");
            require(cps[i].chDigest == prev.chDigest, "CH changed");
            _store(bs[i], cps[i], sigs[i]);
        }
        emit RedactionFinalized(bid, bs.length);
    }

    // ---------------- Phase 6 ----------------
    function anchorRai(uint64 epoch, bytes32 cpA) external onlyOrdering {
        raiCheckpoints[epoch] = cpA;
        emit RaiCheckpoint(epoch, cpA);
    }

    function _store(uint256 b, Checkpoint calldata cp, bytes calldata sig) internal {
        Checkpoint memory c = cp;
        c.sigDigest = keccak256(sig);
        checkpoints[b] = c;
        emit CheckpointAnchored(b, cp.vb, cp.mr);
    }
}

/// @notice Baselines: per-request redaction state as prescribed by each scheme (Table V column 3).
contract BaselineRedactionLog {
    struct Record {
        bytes32 tid;
        bytes32 newCommit;
        bytes32 evidence; // e.g. H(sig^c) for Xue et al. [33]; zero for hash-only schemes
        uint64 version;
    }

    mapping(uint256 => Record) public records;
    uint256 public count;

    event Redacted(uint256 indexed id, bytes32 tid, uint64 version);

    function recordRedaction(bytes32 tid, bytes32 newCommit, uint64 version, bytes calldata evidence) external {
        records[count] = Record(tid, newCommit, evidence.length > 0 ? keccak256(evidence) : bytes32(0), version);
        emit Redacted(count, tid, version);
        count++;
    }
}
