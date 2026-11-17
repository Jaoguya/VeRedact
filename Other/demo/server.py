"""Live class demo: one VeRedact-PQ redaction, built from the project's own modules.

    python Other/demo/server.py          then open http://localhost:8765

Real code, loaded unchanged from Benchmark/src/veredact_bench/methods/veredact/:
  crypto/hashing.py   H, HV (domain-separated SHA3-256)          crypto/pqsig.py   ML-DSA-65 (pqcrypto backend)
  crypto/pqch_sis.py  SIS chameleon hash, dealerless 5-of-7 DKG  ds/merkle.py      Merkle tree, proofs, update
and the same formulas as protocol/ledger.py (Phase 2) and protocol/veredact.py (Phases 3-5):
  D_i = H(m_i, rho_i)   I_i = H(TID, owner, DT, PID, ts, Tag)   L_i = H(I_i, D_i)   CH_b = PQCH(MR_b; r_b)
  A_b signed by the checkpoint authority over H(b, CH_b, MR_b, H(r_b), v_b, ts)

Left out (they run in the AWS benchmark, not here): the STARK policy proof, SA-RLI/RAI indexes, CORA/SFMR across
many batches, BatchAttest/RoundCheckpoint, the Besu chain. Timings are this machine; paper numbers are AWS.
Needs: numpy, pqcrypto. First start runs the DKG (~15 s) and caches it in Other/demo/.cache/.
"""

import copy
import json
import os
import sys
import time
import types
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
VR = HERE.parents[1] / "Benchmark/src/veredact_bench/methods/veredact"
# Load the real modules without the package __init__ files, which pull in the Rust STARK extension we do not use.
for name, sub in (("vr", VR), ("vr.crypto", VR / "crypto"), ("vr.ds", VR / "ds")):
    pkg = types.ModuleType(name)
    pkg.__path__ = [str(sub)]
    sys.modules[name] = pkg
from vr.crypto import pqch_sis as pq  # noqa: E402
from vr.crypto import pqsig  # noqa: E402
from vr.crypto.hashing import HV, H  # noqa: E402
from vr.ds.merkle import MerkleTree, verify_proof  # noqa: E402

N_MEMBERS, T = 7, 5  # the paper's default committee: t = floor(2n/3) + 1
B, E, DT, PID = 17, 1, "record", "P0"  # batch id, epoch, data type, policy (as in Phase 2)
TXS = [
    ("Alice", "Alice -> Bob  1,200 THB  (rent)"),
    ("Carol", "Carol -> Dan  350 THB  (lunch)"),
    ("Somchai", "Somchai -> Clinic  5,000 THB  | phone 081-234-5678 | ID 1-1037-02345-67-8"),
    ("Eve", "Eve -> Frank  90 THB  (coffee)"),
    ("Grace", "Grace -> Heidi  2,500 THB  (tuition)"),
    ("Ivan", "Ivan -> Judy  780 THB  (books)"),
    ("Ken", "Ken -> Leo  15,000 THB  (laptop)"),
    ("Mallory", "Mallory -> Nina  60 THB  (bus)"),
]


def ms(t0):
    return round((time.perf_counter() - t0) * 1000, 2)


def hx(b: bytes, n=16):
    return b.hex()[:n]


class Ledger:
    def __init__(self):
        print(f"setup: ML-DSA-65 keys and the {T}-of-{N_MEMBERS} PQCH committee (DKG cached after the first run)...")
        t0 = time.perf_counter()
        self.sig = pqsig.MLDSA65Pqcrypto()
        self.ch = pq.SISChameleonHash(pq.default_params(n=256, k=16), seed=20261118, cache_dir=HERE / ".cache")
        self.pk_ch, self.shares = self.ch.dkeygen(N_MEMBERS, T)  # each member holds ONE share of the trapdoor
        self.committee = {k: self.sig.keygen() for k in range(1, N_MEMBERS + 1)}  # their ML-DSA approval keys
        self.vps, self.cpa = self.sig.keygen(), self.sig.keygen()  # validation service, checkpoint authority
        self.owners = {o: self.sig.keygen() for o, _ in TXS}  # data owners (they also request redactions)
        print(f"  ready in {time.perf_counter() - t0:.1f} s")
        self.reset()

    # ------------------------------------------------------------------ Phase 2: commit the batch
    def reset(self):
        self.tx = []
        for pos, (owner, m) in enumerate(TXS):
            tid = f"TX-{B}-{pos}".encode()
            ts, tag = 1_731_000_000 + pos, H(tid, os.urandom(16), pos)
            rho = os.urandom(32)
            D = H(m, rho)  # salted content commitment
            sigma = self.sig.sign(self.owners[owner].sk, H(tid, D, DT, PID, ts))  # owner signs D, never m
            I = H(tid, owner, DT, PID, ts, tag)  # non-redactable identity binding
            self.tx.append(
                {"tid": tid, "owner": owner, "m": m, "rho": rho, "D": D, "I": I, "ts": ts, "sigma": sigma, "D0": D}
            )
        self.tree = MerkleTree([H(t["I"], t["D"]) for t in self.tx])  # L_i = H(I_i, D_i)
        self.r = self.ch.sample_r()
        self.CH = self.ch.hash(self.pk_ch, self.tree.root, self.r)  # the block ID: never changes
        self.v, self.log = 0, []
        self._checkpoint()

    def _checkpoint(self):
        """A_b, signed by the checkpoint authority over H(r_b) rather than the 64 KiB r_b (as in ledger.py)."""
        self.ts_cp = int(time.time())
        self.r_digest = H(self.r.tobytes())
        self.cp_msg = H(B, self.CH, self.tree.root, self.r_digest, self.v, self.ts_cp)
        self.cp_sig = self.sig.sign(self.cpa.sk, self.cp_msg)

    def checks(self) -> dict:
        """What any verifier can check about the block right now."""
        return {
            "pqch": self.ch.verify(self.pk_ch, self.CH, self.tree.root, self.r),
            "checkpoint": self.sig.verify(self.cpa.pk, self.cp_msg, self.cp_sig),
        }

    def state(self) -> dict:
        return {
            "txs": [
                {"m": t["m"], "D": hx(t["D"]), "leaf": hx(H(t["I"], t["D"])), "redacted": t["D"] != t["D0"]}
                for t in self.tx
            ],
            "root": self.tree.root.hex(),
            "ch": H(self.CH).hex(),  # fingerprint of the 1 KiB lattice hash
            "ch_bytes": len(self.CH),
            "r": hx(self.r_digest),
            "v": self.v,
            "checks": self.checks(),
            "sig_bytes": self.sig.sig_size,
            "log": self.log,
            "n": N_MEMBERS,
            "t": T,
        }

    # ------------------------------------------------------------------ Phases 3-5: one redaction
    def redact(self, i: int, m_new: str, members: list[int]) -> dict:
        tx, steps = self.tx[i], []
        before = {"m": tx["m"], "D": hx(tx["D"]), "leaf": hx(H(tx["I"], tx["D"])), "root": hx(self.tree.root),
                  "r": hx(self.r_digest), "ch": hx(H(self.CH))}  # fmt: skip

        # Phase 3: the owner asks; the VPS checks the ML-DSA signature on H(R_i)
        t0 = time.perf_counter()
        rho_new = os.urandom(32)
        D_new = H(m_new, rho_new)
        ts_r, n_r = int(time.time() * 1000), os.urandom(16)
        hR = H(tx["owner"], tx["tid"], "modify", D_new, E, ts_r, n_r)
        sigma_R = self.sig.sign(self.owners[tx["owner"]].sk, hR)
        ok = self.sig.verify(self.owners[tx["owner"]].pk, hR, sigma_R)
        steps.append({"phase": 3, "what": f"VPS verifies {tx['owner']}'s ML-DSA-65 request signature", "ok": ok,
                      "ms": ms(t0)})  # fmt: skip

        # Phase 4: committee members sign the batch commitment C_B; t valid approvals are required
        RID, BID = os.urandom(8), os.urandom(16)
        C_B = HV("AUTH-BATCH", BID, E, 1, H(RID, hR, D_new), int(time.time()))
        t0 = time.perf_counter()
        approvals = []
        for k in members:
            s = self.sig.sign(self.committee[k].sk, C_B)
            if self.sig.verify(self.committee[k].pk, C_B, s):
                approvals.append(k)
        authorized = len(approvals) >= T
        steps.append({"phase": 4, "what": f"{len(approvals)} committee ML-DSA approvals on C_B verified "
                      f"(need {T} of {N_MEMBERS})", "ok": authorized, "ms": ms(t0)})  # fmt: skip

        # Phase 5: SFMR leaf update + distributed PQCH adaptation (computed even when unauthorized, to SHOW that
        # fewer than t shares cannot produce a valid collision; the real system stops at Phase 4)
        t0 = time.perf_counter()
        old_leaf, new_leaf = H(tx["I"], tx["D"]), H(tx["I"], D_new)
        leaf_ok = verify_proof(self.tree.root, old_leaf, i, self.tree.proof(i))
        tree = copy.deepcopy(self.tree)
        tree.update({i: new_leaf})
        steps.append({"phase": 5, "what": "old leaf proven against MR_b; leaf L_i = H(I_i, D_i') and MR_b updated",
                      "ok": leaf_ok, "ms": ms(t0)})  # fmt: skip
        t0 = time.perf_counter()
        pert, z = self.ch.begin_adapt(self.pk_ch, self.tree.root, self.r, tree.root)
        member_ms, parts = {}, []
        for k in members:  # each member uses ONLY its own trapdoor share
            s = time.perf_counter()
            parts.append(pq.SISChameleonHash.part_adapt(self.shares[k], z))
            member_ms[k] = ms(s)
        r_new = self.ch.combine(pert, z, parts)
        collision = self.ch.verify(self.pk_ch, self.CH, tree.root, r_new)
        steps.append({"phase": 5, "what": f"{len(members)} trapdoor shares combined: PQCH(MR_b'; r_b') = CH_b ?",
                      "ok": collision, "ms": ms(t0)})  # fmt: skip

        done = authorized and leaf_ok and collision
        if done:
            v_old = self.v
            h_pbrp = HV("PBRP", RID, BID, tx["I"], tx["D"], D_new, B, i, v_old, v_old + 1)
            tx.update(m=m_new, rho=rho_new, D=D_new)
            self.tree, self.r, self.v = tree, r_new, v_old + 1
            t0 = time.perf_counter()
            self._checkpoint()
            steps.append({"phase": 5, "what": "checkpoint A_b' re-signed (ML-DSA-65) over H(r_b'), version "
                          f"{v_old} -> {self.v}", "ok": True, "ms": ms(t0)})  # fmt: skip
            self.log.append({"v": f"{v_old} -> {self.v}", "tx": i, "D_old": before["D"], "D_new": hx(D_new),
                             "approvers": approvals, "pbrp": hx(h_pbrp)})  # fmt: skip
        after = {"m": tx["m"] if done else m_new, "D": hx(D_new), "leaf": hx(new_leaf), "root": hx(tree.root),
                 "r": hx(H(r_new.tobytes())), "ch": hx(H(self.ch.hash(self.pk_ch, tree.root, r_new)))}  # fmt: skip
        return {"kind": "redact", "ok": done, "authorized": authorized, "collision": collision, "members": members,
                "steps": steps, "member_ms": member_ms, "before": before, "after": after}  # fmt: skip

    def tamper(self, i: int, m_new: str) -> dict:
        """An attacker rewrites the record WITHOUT the committee: no trapdoor shares, so r cannot be adapted."""
        tx = self.tx[i]
        D_new = H(m_new, os.urandom(32))
        tree = copy.deepcopy(self.tree)
        tree.update({i: H(tx["I"], D_new)})
        forged = self.ch.hash(self.pk_ch, tree.root, self.r)
        cp_still = self.sig.verify(self.cpa.pk, H(B, forged, tree.root, self.r_digest, self.v, self.ts_cp), self.cp_sig)
        steps = [
            {"phase": "-", "what": "attacker recomputes D_i', L_i, MR_b with the OLD r_b (no trapdoor)", "ok": True,
             "ms": 0},
            {"phase": "-", "what": "PQCH(MR_b'; r_b) = CH_b ?", "ok": forged == self.CH, "ms": 0},
            {"phase": "-", "what": "checkpoint signature still valid for the new root ?", "ok": cp_still, "ms": 0},
        ]  # fmt: skip
        before = {"m": tx["m"], "D": hx(tx["D"]), "leaf": hx(H(tx["I"], tx["D"])), "root": hx(self.tree.root),
                  "r": hx(self.r_digest), "ch": hx(H(self.CH))}  # fmt: skip
        after = {"m": m_new, "D": hx(D_new), "leaf": hx(H(tx["I"], D_new)), "root": hx(tree.root),
                 "r": hx(self.r_digest), "ch": hx(H(forged))}  # fmt: skip
        return {"kind": "tamper", "ok": forged == self.CH, "steps": steps, "before": before, "after": after}


LEDGER = None


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):  # keep the projector terminal quiet
        pass

    def _send(self, body: bytes, ctype="application/json"):
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/api/state":
            return self._send(json.dumps(LEDGER.state()).encode())
        return self._send((HERE / "index.html").read_bytes(), "text/html; charset=utf-8")

    def do_POST(self):
        req = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        if self.path == "/api/redact":
            res = LEDGER.redact(int(req["i"]), str(req["text"])[:200], sorted({int(k) for k in req["members"]}))
        elif self.path == "/api/tamper":
            res = LEDGER.tamper(int(req["i"]), str(req["text"])[:200])
        elif self.path == "/api/reset":
            LEDGER.reset()
            res = {"ok": True}
        else:
            return self.send_error(404)
        res["state"] = LEDGER.state()
        self._send(json.dumps(res).encode())


if __name__ == "__main__":
    LEDGER = Ledger()
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    print(f"demo on http://localhost:{port}   (Ctrl+C to stop)", flush=True)
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
