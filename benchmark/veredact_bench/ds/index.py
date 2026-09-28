"""SA-RLI (Phase 2 Step 4) and RAI (Phase 6 Step 1): sharded authenticated indexes.

Both keep S shards, each a Merkle tree over canonically ordered entries; a global Merkle tree
over shard roots gives R_RLI / R_RAI. A set-based membership filter stands in for the per-shard
Cuckoo filter CF_s (same screening semantics: negatives authoritative only when synchronized).
"""
from dataclasses import dataclass, field

from ..crypto.hashing import H, H1, HA, to_int
from .merkle import MerkleTree


@dataclass
class Shard:
    entries: dict = field(default_factory=dict)  # token -> encoded entry
    tree: MerkleTree | None = None
    order: list = field(default_factory=list)
    pos: dict = field(default_factory=dict)  # token -> leaf position
    changed: set = field(default_factory=set)

    def rebuild(self):
        self.order = sorted(self.entries)
        self.pos = {k: i for i, k in enumerate(self.order)}
        self.tree = MerkleTree([self.entries[k] for k in self.order])
        self.changed.clear()

    def refresh(self) -> int:
        """Incremental: in-place entry updates touch only their paths; insertions force a rebuild."""
        if self.tree is None or any(k not in self.pos for k in self.changed):
            self.rebuild()
            return self.tree.hash_ops[0]
        ops = self.tree.update({self.pos[k]: self.entries[k] for k in self.changed})
        self.changed.clear()
        return ops

    @property
    def root(self):
        if self.tree is None:
            self.rebuild()
        return self.tree.root


class ShardedIndex:
    """Generic sharded authenticated index; `shard_fn` maps a token to its shard id."""

    def __init__(self, S: int, shard_hash):
        self.S = S
        self.shard_hash = shard_hash
        self.shards = [Shard() for _ in range(S)]
        self.filters = [set() for _ in range(S)]  # exact membership sets in place of Cuckoo filters CF_s (docs/paper-conformance.md §3)
        self.snapshot = 0
        self.global_tree: MerkleTree | None = None
        self._dirty: set[int] = set()

    def sid(self, token: bytes) -> int:
        return to_int(self.shard_hash(token)) % self.S

    def put(self, token: bytes, entry: bytes):
        s = self.sid(token)
        self.shards[s].entries[token] = entry
        self.shards[s].changed.add(token)
        self.filters[s].add(token)
        self._dirty.add(s)

    def finalize(self) -> bytes:
        """Recompute only dirty shard roots (R_s* rule of Phase 5 Step 4) and the global root."""
        self.last_hash_ops = sum(self.shards[s].refresh() for s in self._dirty)
        self._dirty.clear()
        self.global_tree = MerkleTree([sh.root for sh in self.shards])
        self.snapshot += 1
        return self.global_tree.root

    @property
    def root(self):
        return self.global_tree.root if self.global_tree else self.finalize()

    def lookup(self, token: bytes):
        """Authenticated lookup: (entry, shard proof, global proof) or None if screened out."""
        s = self.sid(token)
        if token not in self.filters[s]:
            return None
        sh = self.shards[s]
        pos = sh.pos[token]
        return sh.entries[token], s, pos, sh.tree.proof(pos), self.global_tree.proof(s)

    def __len__(self):
        return sum(len(s.entries) for s in self.shards)


def sa_rli(S: int) -> ShardedIndex:
    return ShardedIndex(S, H1)


def rai(S_A: int) -> ShardedIndex:
    return ShardedIndex(S_A, HA)
