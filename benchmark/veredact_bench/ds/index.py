"""SA-RLI (Phase 2 Step 4) and RAI (Phase 6 Step 1): sharded authenticated indexes.

Both keep S shards, each a Merkle tree over canonically ordered entries (SA-RLI: by logical bucket
bid = H_2(tau) mod B, then token; RAI: by token); a global Merkle tree over shard roots gives
R_RLI / R_RAI. Each shard has a Cuckoo filter CF_s, synchronized with the finalized snapshot: a
negative is authoritative only when the filter is synchronized; otherwise, and for every positive, the
lookup is authenticated against the shard and global roots.
"""
from dataclasses import dataclass, field

from ..crypto.hashing import H1, H2, HA, to_int
from . import cuckoo
from .merkle import MerkleTree


@dataclass
class Shard:
    entries: dict = field(default_factory=dict)  # token -> encoded entry
    tree: MerkleTree | None = None
    order: list = field(default_factory=list)
    pos: dict = field(default_factory=dict)  # token -> leaf position
    changed: set = field(default_factory=set)
    order_key: object = None  # canonical ordering of tokens inside the shard

    def rebuild(self):
        self.order = sorted(self.entries, key=self.order_key)
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

    def __init__(self, S: int, shard_hash, order_key=None):
        self.S = S
        self.shard_hash = shard_hash
        self.shards = [Shard(order_key=order_key) for _ in range(S)]
        self.filters = [cuckoo.CuckooFilter() for _ in range(S)]  # CF_s
        self._unsynced: list[set] = [set() for _ in range(S)]  # tokens put since the last finalized snapshot
        self.snapshot = 0
        self.global_tree: MerkleTree | None = None
        self._dirty: set[int] = set()

    def sid(self, token: bytes) -> int:
        return to_int(self.shard_hash(token)) % self.S

    def put(self, token: bytes, entry: bytes):
        s = self.sid(token)
        self.shards[s].entries[token] = entry
        self.shards[s].changed.add(token)
        self._unsynced[s].add(token)
        self._dirty.add(s)

    def finalize(self) -> bytes:
        """Recompute only dirty shard roots (R_s* rule of Phase 5 Step 4) and the global root."""
        self.last_hash_ops = sum(self.shards[s].refresh() for s in self._dirty)
        for s in self._dirty:  # synchronize CF_s with the new snapshot
            new = [t for t in self._unsynced[s] if not self.filters[s].contains(t)]
            if not all(self.filters[s].insert(t) for t in new):
                self.filters[s] = cuckoo.build(self.shards[s].entries)
            self._unsynced[s].clear()
        self._dirty.clear()
        self.global_tree = MerkleTree([sh.root for sh in self.shards])
        self.snapshot += 1
        return self.global_tree.root

    @property
    def root(self):
        return self.global_tree.root if self.global_tree else self.finalize()

    def lookup(self, token: bytes):
        """Authenticated lookup: (entry, shard, pos, shard proof, global proof), or None when the token is absent
        (screened out by a synchronized CF_s, or a filter false positive found absent by the lookup)."""
        s = self.sid(token)
        synced = not self._unsynced[s]
        if synced and not self.filters[s].contains(token):
            return None
        sh = self.shards[s]
        if token not in sh.pos:
            return None
        pos = sh.pos[token]
        return sh.entries[token], s, pos, sh.tree.proof(pos), self.global_tree.proof(s)

    def __len__(self):
        return sum(len(s.entries) for s in self.shards)


def sa_rli(S: int, B: int) -> ShardedIndex:
    return ShardedIndex(S, H1, order_key=lambda tau: (to_int(H2(tau)) % B, tau))


def rai(S_A: int) -> ShardedIndex:
    return ShardedIndex(S_A, HA)
