"""Builds the crypto + ledger environment shared by all experiments."""
import time

from .config import D
from .crypto import Crypto
from .crypto.pqzk import SimulatedSTARK
from .protocol.ledger import Ledger
from .workload import payloads


def make_crypto(classical=False):
    return Crypto(zk=SimulatedSTARK(D.zk_prove_ms, D.zk_verify_ms, D.zk_proof_bytes), ch_dim=D.ch_dim,
                  classical_sigs=classical, policy_ms=D.policy_ms)


def make_ledger(size, n=D.n, t=D.t, N=D.N, classical=False, seed=0, verbose=True):
    t0 = time.time()
    c = make_crypto(classical)
    L = Ledger(c, n=n, t=t, N=N, S=D.S, S_A=D.S_A)
    L.commit_transactions(payloads(size, seed=seed))
    c.reset()
    if verbose:
        print(f"[env] ledger {size} tx / {len(L.batches)} batches, n={n} t={t}, sig={c.sig.name} "
              f"({time.time() - t0:.1f}s)", flush=True)
    return L
