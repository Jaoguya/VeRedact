"""CORA: Cost- and Overlap-Aware Redaction Aggregation (VeRedact-optimize.tex, Phase 4 Step 1).

Selects validated requests for one authorization round by the estimated redaction cost
    C_CORA(S) = w_CH * |Omega(S)| + w_F * sum_b |F_b(L_b(S))|,
where Omega(S) are the affected transaction batches and F_b the external Merkle frontier of the selected
positions in batch b (the siblings SFMR needs; equal to MerkleTree.multiproof). Greedy realization as in the
manuscript: mandatory requests (waited >= T_max) first, oldest first; then the smallest marginal cost, ties
broken by admission time and RID. Locality decides only the grouping, never eligibility.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Candidate:
    rid: bytes
    b: int
    pos: int
    admitted: float  # ts_i^adm (s, same clock as `now`)


def frontier_size(positions, depth: int) -> int:
    """|F_b(L)| for leaf positions L in a padded binary tree of the given depth."""
    known, size = set(positions), 0
    for _ in range(depth):
        size += sum(1 for i in known if i ^ 1 not in known)
        known = {i // 2 for i in known}
    return size


def cora_select(queue, now: float, target: int, b_max: int, depth: int, t_max: float, w_ch: float, w_f: float):
    """The CORA-selected requests, in selection order (at most max(target, mandatory up to b_max))."""
    order = sorted(queue, key=lambda c: (c.admitted, c.rid))
    mandatory = [c for c in order if now - c.admitted >= t_max][:b_max]
    limit = max(target, len(mandatory))
    chosen, picked = list(mandatory), {c.rid for c in mandatory}
    positions: dict[int, set] = {}
    for c in chosen:
        positions.setdefault(c.b, set()).add(c.pos)

    def marginal(c):
        if c.b not in positions:
            return w_ch + w_f * frontier_size({c.pos}, depth)
        P = positions[c.b]
        return w_f * (frontier_size(P | {c.pos}, depth) - frontier_size(P, depth))

    rest = [c for c in order if c.rid not in picked]
    cost = {c.rid: marginal(c) for c in rest}
    while len(chosen) < limit and rest:
        best = min(rest, key=lambda c: (cost[c.rid], c.admitted, c.rid))
        rest.remove(best)
        chosen.append(best)
        positions.setdefault(best.b, set()).add(best.pos)
        for c in rest:  # only candidates in the batch that just changed have a new marginal cost
            if c.b == best.b:
                cost[c.rid] = marginal(c)
    return chosen
