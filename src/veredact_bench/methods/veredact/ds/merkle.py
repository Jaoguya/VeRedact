"""Binary SHA3-256 Merkle tree with single proofs, query-scoped multiproofs, and BIMC batch update.

Used for transaction batches (MR_b), SA-RLI / RAI shard and global roots, and the ABRRR request root R_e^VR.
Leaves are padded to a power of two with an empty-leaf constant so positions are stable.
"""

from ..crypto.hashing import H

EMPTY = H("merkle-empty-leaf")


def _node(a, b, counter=None):
    if counter is not None:
        counter[0] += 1
    return H("node", a, b)


def _leaf(x, counter=None):
    if counter is not None:
        counter[0] += 1
    return H("leaf", x)


class MerkleTree:
    def __init__(self, leaves: list[bytes]):
        size = 1
        while size < max(1, len(leaves)):
            size *= 2
        self.n = len(leaves)
        self.size = size
        self.hash_ops = [0]
        level = [_leaf(x, self.hash_ops) for x in leaves] + [EMPTY] * (size - len(leaves))
        self.levels = [level]
        while len(level) > 1:
            level = [_node(level[i], level[i + 1], self.hash_ops) for i in range(0, len(level), 2)]
            self.levels.append(level)

    @property
    def root(self) -> bytes:
        return self.levels[-1][0]

    def proof(self, pos: int) -> list[bytes]:
        path, i = [], pos
        for level in self.levels[:-1]:
            path.append(level[i ^ 1])
            i //= 2
        return path

    def multiproof(self, positions) -> dict:
        """Minimal sibling set authenticating all `positions` at once (shared paths counted once)."""
        known = set(positions)
        needed = {}
        for depth, level in enumerate(self.levels[:-1]):
            parents = set()
            for i in known:
                sib = i ^ 1
                if sib not in known:
                    needed[(depth, sib)] = level[sib]
                parents.add(i // 2)
            known = parents
        return needed

    def update(self, changes: dict[int, bytes]) -> int:
        """BIMC.Update: apply all leaf changes, recomputing each shared ancestor once. Returns hash ops."""
        ops = [0]
        dirty = set()
        for pos, new_leaf in changes.items():
            self.levels[0][pos] = _leaf(new_leaf, ops)
            dirty.add(pos // 2)
        for depth in range(1, len(self.levels)):
            below = self.levels[depth - 1]
            nxt = set()
            for i in dirty:
                self.levels[depth][i] = _node(below[2 * i], below[2 * i + 1], ops)
                nxt.add(i // 2)
            dirty = nxt
        return ops[0]

    def update_independent(self, changes: dict[int, bytes]) -> int:
        """No-BIMC variant: every modification recomputes its full path separately."""
        total = 0
        for pos, leaf in changes.items():
            total += self.update({pos: leaf})
        return total


def verify_proof(root: bytes, leaf: bytes, pos: int, path: list[bytes]) -> bool:
    h = H("leaf", leaf)
    for sib in path:
        h = H("node", h, sib) if pos % 2 == 0 else H("node", sib, h)
        pos //= 2
    return h == root


def verify_multiproof(root: bytes, leaves: dict[int, bytes], proof: dict, depth: int) -> tuple[bool, int]:
    """Verify a multiproof; returns (ok, hash_ops)."""
    ops = 0
    level = {pos: H("leaf", x) for pos, x in leaves.items()}
    ops += len(level)
    for d in range(depth):
        nxt = {}
        for i in set(p // 2 for p in level):
            left = level.get(2 * i, proof.get((d, 2 * i)))
            right = level.get(2 * i + 1, proof.get((d, 2 * i + 1)))
            if left is None or right is None:
                return False, ops
            nxt[i] = H("node", left, right)
            ops += 1
        level = nxt
    return level.get(0) == root, ops
