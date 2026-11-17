"""Live class demo: the whole VeRedact-PQ protocol, Phase 1 to Phase 6, run by the project's own code.

    python Other/demo/server.py          then open http://localhost:8765

This is NOT a re-implementation. It opens the real system exactly as the tests and the benchmark do
(open_system(cfg, "veredact", ds) on the smoke tier) and calls its phases one by one:
  Phases 1-2  Ledger setup + commit_transactions   keys, 5-of-7 PQCH DKG, policies, STARK credential registry,
                                                   4,096 transactions in 16 batches, SA-RLI, signed checkpoints
  Phase 3     VeRedactScheme.prepare / authorize   requester: ML-DSA-65 signature + PQZK STARK proof;
                                                   VPS: SA-RLI lookup, signature, policy, FreshLeaf, PQZK, BatchAttest
  Phase 4     VeRedactPQ.select_round (CORA) + authorize_batch   t committee ML-DSA approvals on C_B
  Phase 5     redact                               SFMR + distributed PQCH adaptation + RoundCheckpoint
  Phase 6     index_records + audit                RAI, signed query, SAVER verification per record
Attacks are the system's own fault injection: request faults (sig, zk, policy, stale, replay, absent) used by
Exp. 1, and audit tampering (modified, substituted, stale, forged_approval, forged_proof) used by Exp. 4.

Smoke tier = smaller sizes, same security parameters: 4,096 transactions instead of 10^5, a 128-slot credential
registry instead of 2^15, and the in-process ledger instead of the 7-validator Besu network the benchmark uses.
Timings are this machine; the paper's numbers come from AWS. Needs the Benchmark package's dependencies plus the
STARK extension (see README.md). Setup takes ~10 s.
"""

import copy
import dataclasses
import json
import os
import sys
import time
import tomllib
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
BENCH = HERE.parents[1] / "Benchmark"
sys.path.insert(0, str(BENCH / "src"))
from veredact_bench.data.dataset import build_dataset  # noqa: E402
from veredact_bench.evaluation.common import open_system  # noqa: E402
from veredact_bench.methods.scheme import AuditQuery, RedactionRequest  # noqa: E402
from veredact_bench.methods.veredact.crypto.hashing import H  # noqa: E402
from veredact_bench.utils.config import load  # noqa: E402

PII = "Somchai -> Clinic 5,000 THB | phone 081-234-5678 | ID 1-1037-02345-67-8"
TARGET = 3 * 256 + 17  # transaction index: batch 3, position 17
REQUEST_FAULTS = ("", "sig", "zk", "policy", "stale", "replay", "absent")
AUDIT_FAULTS = ("", "modified", "substituted", "stale", "forged_approval", "forged_proof")


def hx(b, n=16) -> str:
    return (b if isinstance(b, bytes) else bytes(b)).hex()[:n]


def ms(t0) -> float:
    return round((time.perf_counter() - t0) * 1000, 2)


RPC = "http://127.0.0.1:8545"  # Other/demo/chain.sh up: 4 Besu QBFT validators in Docker
CHAIN_VALIDATORS = 4


def chain_up() -> bool:
    """Is the demo's Besu chain answering? Then the system anchors on it; otherwise the in-process ledger."""
    body = json.dumps({"jsonrpc": "2.0", "method": "eth_blockNumber", "params": [], "id": 1}).encode()
    req = urllib.request.Request(RPC, body, {"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=1.5) as r:
            return int(json.load(r)["result"], 16) >= 1
    except Exception:
        return False


class Demo:
    def __init__(self):
        self.reset()

    # ------------------------------------------------------------------ Phases 1-2 (setup, untimed in the paper)
    def reset(self):
        print("setting up the real VeRedact-PQ system (smoke tier)...", flush=True)
        t0 = time.perf_counter()
        cfg = copy.deepcopy(load("smoke"))
        self.real_chain = chain_up()
        if self.real_chain:  # the project's own Besu backend (evaluation/anchor.py BesuAnchor), as on AWS
            cfg["ledger"].update(backend="besu", rpc_url=RPC, validators=CHAIN_VALIDATORS)
            with open(BENCH / "configs/aws.toml", "rb") as f:  # the public Besu dev key, funded in genesis only
                os.environ.setdefault("VRPQ_BESU_KEY", tomllib.load(f)["besu"]["dev_private_key"])
        print(f"  ledger: {'Besu QBFT at ' + RPC if self.real_chain else 'in-process (no chain running)'}", flush=True)
        ds = build_dataset(cfg, n_requests=64)
        t = ds.transactions[TARGET]
        ds.transactions[TARGET] = dataclasses.replace(t, payload=PII.encode())  # the record with personal data
        self.cfg, self.ds = cfg, ds
        self.s = open_system(cfg, "veredact", ds)
        self.setup_s = round(time.perf_counter() - t0, 1)
        self.L, self.c = self.s.ledger, self.s.crypto
        self.tid = t.tid
        self.seq = 10_000
        self.round = 0
        self.phase = 2  # Phases 1-2 are done by setup; the page reveals them on demand
        self.pending, self.batch_auth, self.batch, self.recs = [], None, [], []
        print(f"  ready in {self.setup_s} s", flush=True)

    def ops(self, op=None) -> int:
        return sum(1 for o, _ in self.L.anchor.oplog if op is None or o == op)

    def chain(self) -> dict:
        a = self.L.anchor
        if not self.real_chain:
            return {"real": False}
        return {"real": True, "validators": CHAIN_VALIDATORS, "block": a.w3.eth.block_number, "contract": a.reg.address}

    def marks(self):
        """Where the chain stood before a phase: (anchoring futures, receipts) so far."""
        return len(self.s.p.pending_anchor), len(self.L.anchor.receipts)

    def mined(self, mark) -> list:
        """Wait until the phase's anchoring transactions are mined; describe each from its receipt."""
        k0, r0 = mark
        futs = self.s.p.pending_anchor[k0:]
        for f in futs:
            f.result()
        rec = self.L.anchor.receipts
        deadline = time.time() + 2  # receipts are recorded by a done-callback, just after result() returns
        while len(rec) < r0 + len(futs) and time.time() < deadline:
            time.sleep(0.02)
        return [{"op": op, "s": round(ledger_ms / 1000, 1), "gas": gas} for op, ledger_ms, gas in list(rec)[r0:]]

    def batch_view(self, b) -> dict:
        bt = self.L.batches[b]
        return {"b": b, "v": bt.v, "MR": hx(bt.tree.root), "CH": H(bt.ch).hex(), "r": hx(H(bt.r.tobytes()))}

    def state(self) -> dict:
        tx = self.L.txs[self.tid]
        return {
            "phase": self.phase,
            "round": self.round,
            "target": {"tid": self.tid.decode(), "m": tx.m.decode(errors="replace"), "b": tx.b, "pos": tx.pos},
            "batches": [self.batch_view(b) for b in sorted(self.L.batches)],
            "n": self.L.n,
            "t": self.L.t,
            "records": len(self.s.p.records),
            "anchors": self.ops(),
            "chain": self.chain(),
        }

    def phase1(self) -> dict:
        L, c = self.L, self.c
        pol = next(iter(L.policies.values()))
        share = next(iter(L.td.values()))
        return {
            "facts": [
                ("ML-DSA-65 keys", f"{4 + len(L.requesters) + L.n} parties"),
                ("Trapdoor", f"{L.t}-of-{L.n} shares ({share.S.shape[0]}×{share.S.shape[1]}), never whole"),
                ("Policies", f'{len(L.policies)} · e.g. {pol.PID}: {pol.body.split(";")[1].strip()}'),
                ("Credentials", f"STARK root {c.zk.root[0]:x}"[:22] + "…"),
                ("Chain", f"Besu QBFT · {CHAIN_VALIDATORS} validators · {L.anchor.reg.address[:10]}…"
                          if self.real_chain else "in-process ledger"),
                ("Registered", f"{self.ops('policy_register')} policies + {self.ops('committee_register')} committee"),
            ],  # fmt: skip
            "checks": [{"ok": True, "what": f"Ready in {self.setup_s} s"}],
        }

    def phase2(self) -> dict:
        L = self.L
        tx = L.txs[self.tid]
        cp = L.checkpoints[tx.b]
        leaf = H(tx.I, tx.D)
        return {
            "facts": [
                ("Ledger", f"{len(L.txs):,} transactions · {len(L.batches)} batches"),
                ("Record", f"{tx.TID.decode()} · batch {tx.b}, position {tx.pos}"),
                ("D = H(m‖ρ)", f"{hx(tx.D)}… · owner-signed"),
                ("L = H(I‖D)", f"{hx(leaf)}…"),
                ("Merkle root", f"{hx(L.batches[tx.b].tree.root)}…"),
                ("Checkpoints", f"{self.ops('batch_checkpoint')} anchored · SA-RLI {hx(cp.R_RLI)}…"),
            ],  # fmt: skip
            "checks": [{"ok": L.c.ch.verify(L.pk_ch, L.batches[tx.b].ch, L.batches[tx.b].tree.root,
                                            L.batches[tx.b].r), "what": "Batch ID = PQCH(MR ; r)"}],
        }  # fmt: skip

    # ------------------------------------------------------------------ Phase 3: requests -> VPS
    def _request(self, tid, payload: str, fault: str = ""):
        """A request by the record's owner (owners double as requesters, as in Phase 2)."""
        self.seq += 1
        owner = self.L.txs[tid].owner % self.ds.requesters
        return RedactionRequest(self.seq, owner, tid, payload.encode(), 0.0, fault)

    def phase3(self, text: str, fault: str) -> dict:
        tx = self.L.txs[self.tid]
        others = [t for t in self.ds.transactions if t.tid != self.tid]
        same = next(t for t in others if self.L.txs[t.tid].b == tx.b)  # shares the target's batch (SFMR)
        bg = [same] + [t for t in others if self.L.txs[t.tid].b not in (tx.b,)][self.round * 7 :: 911][:2]
        reqs = [self._request(t.tid, f"{t.payload.decode(errors='replace')[:12]}… [REDACTED]") for t in bg]
        reqs.append(self._request(self.tid, text, fault))  # the presenter's request goes last (replay needs a past)
        rows, self.pending = [], []
        for r in reqs:
            t0 = time.perf_counter()
            R = self.s.prepare(r)  # requester side: ML-DSA-65 signature + PQZK STARK proof
            prove = ms(t0)
            a = self.s.authorize(r, R)  # VPS: Phase 3
            mine = r.tid == self.tid or r.fault == "absent"
            row = {"mine": mine, "tid": r.tid.decode(), "fault": r.fault, "ok": a.ok, "reason": a.reason,
                   "prove_ms": prove, "vps_ms": round(a.crypto_ms, 2), "proof_B": len(R.proof or b"")}  # fmt: skip
            if a.ok:
                vr = a.handle
                row.update(b=vr.b, pos=vr.pos, rid=hx(vr.RID), h_st=hx(vr.h_st), v_snap=vr.v_snap,
                           window=getattr(vr.att, "w", -1))  # fmt: skip
                self.pending.append(a)
            rows.append(row)
        self.phase = 3
        return {"requests": rows, "queue": len(self.pending)}

    # ------------------------------------------------------------------ Phase 4: CORA + committee
    def phase4(self) -> dict:
        now = time.time()
        chosen = self.s.p.select_round([(a.handle, now) for a in self.pending], now, arrival_rate=4.0)  # CORA
        ids = {v.RID for v in chosen}
        self.batch = [a for a in self.pending if a.handle.RID in ids]
        mark = self.marks()
        self.batch_auth, ph4 = self.s.authorize_batch(self.batch)
        ba = self.batch_auth
        self.phase = 4
        return {
            "selected": len(self.batch),
            "queued": len(self.pending),
            "batches": sorted({a.handle.b for a in self.batch}),
            "ok": ba is not None,
            "BID": hx(ba.BID) if ba else "",
            "C_B": hx(ba.C_B) if ba else "",
            "R_VR": hx(ba.R_VR) if ba else "",
            "gamma": hx(ba.gamma) if ba else "",
            "approvals": [k + 1 for k, _ in ba.approvals] if ba else [],
            "sig_B": self.c.sig.sig_size,
            "ms": round(ph4, 2),
            "anchored": self.mined(mark),
        }

    # ------------------------------------------------------------------ Phase 5: SFMR + PQCH + checkpoint
    def phase5(self) -> dict:
        bs = sorted({a.handle.b for a in self.batch})
        before = {b: self.batch_view(b) for b in bs}
        mark = self.marks()
        res = self.s.redact(self.batch, self.batch_auth)
        after = {b: self.batch_view(b) for b in bs}
        k = sum(o.ok for o in res.outcomes)
        self.recs = self.s.p.records[-k:] if k else []
        cp = self.L.checkpoints[bs[0]]
        tx = self.L.txs[self.tid]
        self.phase, self.round = 5, self.round + 1
        return {
            "executed": k,
            "requests": len(self.batch),
            "adaptations": res.ch_adaptations,
            "crypto_ms": round(res.crypto_ms, 2),
            "frontier": self.s.p.last_exec.get("frontier", 0),
            "batches": [{"before": before[b], "after": after[b]} for b in bs],
            "target_m": tx.m.decode(errors="replace"),
            "round_root": hx(cp.round_root),
            "round_sig_B": len(cp.round_sigma),
            "round_path": len(cp.round_path),
            "anchored": self.mined(mark),
            "ok": all(after[b]["CH"] == before[b]["CH"] for b in bs),
        }

    def attack5(self, kind: str) -> dict:
        """Against the record's batch, with the system's real PQCH key and DKG shares: 4 members alone, or an
        outsider with no trapdoor. Nothing is written either way."""
        L, ch = self.L, self.L.c.ch
        tx = L.txs[self.tid]
        bt = L.batches[tx.b]
        tree = copy.deepcopy(bt.tree)
        tree.update({tx.pos: H(tx.I, H(b"forged content", b"rho"))})
        if kind == "four":
            pert, z = ch.begin_adapt(L.pk_ch, bt.tree.root, bt.r, tree.root)
            parts = [ch.part_adapt(L.td[k], z) for k in sorted(L.td)[: L.t - 1]]
            r_new = ch.combine(pert, z, parts)
            ok = ch.verify(L.pk_ch, bt.ch, tree.root, r_new)
            what = f"{L.t - 1} of {L.n} members combine their real trapdoor shares"
        else:
            ok = ch.hash(L.pk_ch, tree.root, bt.r) == bt.ch
            what = "an outsider edits the record and keeps the old randomness r"
        return {"kind": kind, "what": what, "ok": ok, "CH": H(bt.ch).hex()}

    # ------------------------------------------------------------------ Phase 6: RAI + audit
    def phase6(self, tamper: str) -> dict:
        mark = self.marks()
        t0 = time.perf_counter()
        self.s.index_records()  # RAI entries for every record + CP_e^A anchored
        idx_ms = ms(t0)
        recs = self.s.p.records
        mine = max((i for i, r in enumerate(recs) if r.TID == self.tid), default=0)
        q = AuditQuery(records=len(recs), tamper={mine: tamper} if tamper else {}, deep=tamper == "forged_proof")
        res = self.s.audit(q)
        self.phase = 6
        return {
            "records": [
                {
                    "i": i,
                    "tid": r.TID.decode(),
                    "b": r.b,
                    "v": f"{r.v_b}→{r.v_b_new}",
                    "ok": bool(res.accepted[i]),
                    "mine": i == mine,
                    "tampered": (res.tampered or {}).get(i, ""),
                }
                for i, r in enumerate(recs)
            ],  # fmt: skip
            "bytes": res.evidence_bytes,
            "gen_ms": round(res.retrieval_ms, 2),
            "verify_ms": round(res.verify_ms, 2),
            "index_ms": idx_ms,
            "nodes": res.verified_nodes,
            "deep": tamper == "forged_proof",
            "anchored": self.mined(mark),
            "semantics": res.semantics,
        }


DEMO = None


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, body: bytes, ctype="application/json"):
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/api/state":
            return self._send(json.dumps(DEMO.state()).encode())
        if self.path == "/api/chain":  # polled by the page: the block height keeps rising while the chain runs
            return self._send(json.dumps(DEMO.chain()).encode())
        return self._send((HERE / "index.html").read_bytes(), "text/html; charset=utf-8")

    def do_POST(self):
        req = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        try:
            p = self.path
            if p == "/api/phase1":
                res = DEMO.phase1()
            elif p == "/api/phase2":
                res = DEMO.phase2()
            elif p == "/api/phase3":
                fault = req.get("fault", "") if req.get("fault", "") in REQUEST_FAULTS else ""
                res = DEMO.phase3(str(req.get("text", ""))[:200] or "[REDACTED]", fault)
            elif p == "/api/phase4":
                res = DEMO.phase4()
            elif p == "/api/phase5":
                res = DEMO.phase5()
            elif p == "/api/attack5":
                res = DEMO.attack5("four" if req.get("kind") == "four" else "outsider")
            elif p == "/api/phase6":
                res = DEMO.phase6(req.get("tamper", "") if req.get("tamper", "") in AUDIT_FAULTS else "")
            elif p == "/api/reset":
                DEMO.reset()
                res = {}
            else:
                return self.send_error(404)
        except Exception as e:  # show the error on the page instead of a dead button
            res = {"error": f"{type(e).__name__}: {e}"}
        res["state"] = DEMO.state()
        self._send(json.dumps(res, default=str).encode())


if __name__ == "__main__":
    DEMO = Demo()
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    print(f"demo on http://localhost:{port}   (Ctrl+C to stop)", flush=True)
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
