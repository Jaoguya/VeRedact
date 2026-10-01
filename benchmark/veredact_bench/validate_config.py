"""validate-config: gate every experiment behind a config check.

    python -m veredact_bench.validate_config config/experiment.toml

Exit 0 = no errors (warnings may remain) · 1 = errors, do not run · 2 = unreadable.

Most checks target errors that crash nothing and silently void the comparison: a baseline instantiated
below the security level looks faster, a threshold below the stated majority looks cheaper, a sweep that
never reaches saturation looks linear, a smoke-tier ledger backend reports in-memory time as consensus.
"""
import math
import sys
import tomllib
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
REFERENCE_TIER = REPO / "config" / "experiment.toml"


def _keys(d, prefix=""):
    out = set()
    for k, v in d.items():
        out |= _keys(v, f"{prefix}{k}.") if isinstance(v, dict) else {prefix + k}
    return out


def validate(path: Path) -> tuple[list[str], list[str]]:
    c = tomllib.loads(path.read_text())
    tier = c["meta"]["tier"]
    final = tier == "experiment"
    err, warn = [], []
    E = err.append
    W = warn.append

    # ---- structure: every tier carries exactly the reference keys ------------------------------------
    ref = _keys(tomllib.loads(REFERENCE_TIER.read_text()))
    got = _keys(c)
    if got != ref:
        E(f"keys differ from config/experiment.toml: missing {sorted(ref - got)} extra {sorted(got - ref)}")

    # ---- security uniformity ---------------------------------------------------------------------------
    sec = c["security"]
    if sec["nist_level"] != 3 or sec["signature"] != "ML-DSA-65":
        E("manuscript fixes NIST level 3 / ML-DSA-65")
    z = sec["pqzk"]
    zk_bits = z["queries"] * math.log2(z["blowup"]) + z["grinding_bits"]
    if zk_bits < 128:
        E(f"PQZK conjectured soundness {zk_bits:.0f} bits < 128 (queries*log2(blowup)+grinding)")
    if (z["registry_depth"] + 1) & z["registry_depth"]:
        E("pqzk.registry_depth + 1 must be a power of two (STARK trace length)")
    if 2 ** z["registry_depth"] < c["dataset"]["requesters"]:
        E("credential registry smaller than dataset.requesters")
    classical_min = 3072 if final else 1024
    if c["baselines"]["S1"]["accumulator_rsa_bits"] < classical_min:
        (E if final else W)("baselines.S1.accumulator_rsa_bits < 3072: below 128-bit")
    for s in ("S13", "S34"):
        if c["baselines"][s]["rsa_bits"] < classical_min:
            (E if final else W)(f"baselines.{s}.rsa_bits {c['baselines'][s]['rsa_bits']} < 3072: below 128-bit, "
                                "the baseline would look faster than its secure instantiation")
    for s in ("S1", "S34"):
        if c["baselines"][s]["pairing"].upper() in ("BN254", "BN256", "TYPE A", "TYPE E"):
            E(f"baselines.{s}.pairing below 128-bit security (BN254 is ~100-110 bits after exTNFS)")

    # ---- ledger ----------------------------------------------------------------------------------------
    L = c["ledger"]
    if final and L["backend"] != "besu":
        E("experiment tier must use ledger.backend = besu: in_process LedgerTime is not consensus cost")
    if L["validators"] < 4:
        E("QBFT needs >= 4 validators (3f+1, f >= 1)")
    if L["receipt_poll_ms"] * 10 > L["block_period_s"] * 1000:
        E("ledger.receipt_poll_ms must be <= block period / 10, or finality latency is dominated by polling")
    if c["dataset"]["organisations"] != L["validators"]:
        W("dataset.organisations != ledger.validators (manuscript: one validator per organisation)")

    # ---- VeRedact-PQ + fairness of thresholds -----------------------------------------------------------
    v = c["veredact"]
    n, t = v["committee_n"], v["committee_t"]
    if not (2 * n) // 3 + 1 <= t <= n:
        E(f"committee t={t} must satisfy floor(2n/3)+1 <= t <= n (n={n})")
    if not 1 <= v["B_min"] <= v["fixed_batch"] <= v["B_max"]:
        E("need 1 <= B_min <= fixed_batch <= B_max")
    if v["vps_workers"] > c["environment"]["vcpus"]:
        W("vps_workers exceeds vcpus: Exp. 1 would measure CPU contention, not the design")
    for s, (tk, nk) in {"S1": ("threshold_t", "nodes_n"), "S27": ("threshold_t", "redactors_n")}.items():
        b = c["baselines"][s]
        if (b[tk], b[nk]) != (t, n):
            W(f"baselines.{s} threshold ({b[tk]}-of-{b[nk]}) differs from VeRedact ({t}-of-{n}): unequal distribution")

    # ---- dataset / workload ------------------------------------------------------------------------------
    d, w = c["dataset"], c["workload"]
    if d["base_transactions"] < d["leaves_per_batch"]:
        E("base_transactions < leaves_per_batch")
    if not d["payload_min_bytes"] <= d["payload_max_bytes"]:
        E("payload_min_bytes > payload_max_bytes")
    if w["total_requests"] < 10000:
        W(f"workload.total_requests={w['total_requests']} gives < 100 samples above p99")

    # ---- experiments -------------------------------------------------------------------------------------
    x = c["experiments"]
    if sorted(x["exp1"]["rates"]) != x["exp1"]["rates"]:
        E("exp1.rates must be ascending")
    if 0.0 not in x["exp1"]["zipf_sweep"]:
        E("exp1.zipf_sweep must include 0 (uniform targets: the regime where coalescing does not help)")
    if 1 not in x["exp2"]["batch_sizes"]:
        E("exp2.batch_sizes must include 1 (the per-request point every baseline shares)")
    if min(x["exp2"]["committee_sizes"]) < 4:
        E("exp2.committee_sizes must be >= 4")
    if 1 not in x["exp3"]["records_per_batch"]:
        E("exp3.records_per_batch must include 1 (shared-evidence savings disappear there)")
    if max(x["exp3"]["n_Q"]) > w["total_requests"] and final:
        E("exp3.n_Q exceeds the number of redactions the trace can produce")
    if not 0 < x["exp1"]["saturation_tolerance"] < 1 or x["exp1"]["client_threads"] < 1:
        E("exp1.saturation_tolerance must be in (0, 1) and exp1.client_threads >= 1")
    if x["exp5"]["requests_per_point"] % max(x["exp5"]["batch_sizes"]):
        E("exp5.requests_per_point must be a multiple of max(exp5.batch_sizes)")
    s34 = c["baselines"]["S34"]
    if not 1 <= s34["policy_threshold"] <= s34["policy_attributes"]:
        E("baselines.S34 needs 1 <= policy_threshold <= policy_attributes")
    if final and max(x["exp1"]["rates"]) / min(x["exp1"]["rates"]) < 10:
        E("exp1.rates must span at least one order of magnitude (saturation must be shown, not assumed)")

    # ---- reproducibility ----------------------------------------------------------------------------------
    o = c["output"]
    for k in ("per_request_rows", "record_resolved_config", "record_seed", "record_git_commit", "record_environment"):
        if not o[k]:
            E(f"output.{k} must be true")
    if o["allow_published_numbers_in_tables"]:
        E("output.allow_published_numbers_in_tables must be false")
    if c["meta"]["repetitions"] < 10:
        W(f"meta.repetitions={c['meta']['repetitions']} < 10: no defensible CI unless the pilot's CV justifies it")

    confirms = [ln.strip() for ln in path.read_text().splitlines() if "[CONFIRM]" in ln]
    if confirms:
        W(f"{len(confirms)} [CONFIRM] values still need a decision: grep -n CONFIRM {path.name}")
    return err, warn


def main():
    path = Path(sys.argv[1] if len(sys.argv) > 1 else REFERENCE_TIER)
    try:
        err, warn = validate(path)
    except (OSError, tomllib.TOMLDecodeError, KeyError) as e:
        print(f"cannot validate {path}: {e!r}")
        sys.exit(2)
    for m in err:
        print(f"ERROR   {m}")
    for m in warn:
        print(f"warning {m}")
    print(f"{len(err)} error(s), {len(warn)} warning(s)")
    print("Config is valid." if not err else "Do NOT run experiments with this config.")
    sys.exit(1 if err else 0)


if __name__ == "__main__":
    main()
