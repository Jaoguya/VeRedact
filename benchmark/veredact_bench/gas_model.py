"""Offline EVM gas estimate for the on-chain operations recorded in Ledger.chain (Exp. 5).

This is an ESTIMATE (Shanghai-era schedule) so Exp. 5 can be prototyped without a network.
The paper's numbers must come from Besu transaction receipts: see ../scripts/measure_gas_besu.py,
which replays the same operation log against contracts/VeRedactRegistry.sol.
"""
TX_BASE = 21_000
CALLDATA_NONZERO = 16  # per byte (hashes/signatures are ~all non-zero)
SSTORE_NEW = 22_100  # cold slot, zero -> non-zero
LOG_BASE, LOG_TOPIC, LOG_BYTE = 375, 375, 8

# words written to storage per operation (digests only; PQ signatures are verified off-chain by
# validators and passed as calldata, then emitted/hashed — see contracts/)
STORE_WORDS = {
    "policy_register": 3,
    "committee_register": 3,
    "batch_checkpoint": 6,
    "abrrr_authorization": 2,
    "redaction_finalization": 1,  # + per transition below
    "per_transition": 6,
    "rai_checkpoint": 2,
    "per_request_redaction": 2,
}


def op_gas(op: dict) -> int:
    kind, nbytes = op["op"], op["bytes"]
    words = STORE_WORDS.get(kind, 2)
    if kind == "redaction_finalization":
        words += STORE_WORDS["per_transition"] * op.get("transitions", 1)
    return TX_BASE + CALLDATA_NONZERO * nbytes + SSTORE_NEW * words + LOG_BASE + 2 * LOG_TOPIC + LOG_BYTE * 64


def gas_of(ops, phases=None) -> int:
    return sum(op_gas(o) for o in ops if phases is None or o.get("phase") in phases)
