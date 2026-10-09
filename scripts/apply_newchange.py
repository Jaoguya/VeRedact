"""Build a red-marked preview copy of the manuscript with every overleaf/newchange.md item applied.
The manuscript itself (overleaf/VeRedact-2.tex) is never edited; output: overleaf/revised/VeRedact-2-revised.tex.
Each item: (id, find_start, find_end or None, replacement). Changed text is red; removed text leaves a red tag.
Missing image files are drawn as framed placeholders so the preview compiles without the Overleaf assets.
Usage: python3 scripts/apply_newchange.py"""

import pathlib
import re

SRC = pathlib.Path("overleaf/VeRedact-2.tex")
OUT = pathlib.Path("overleaf/revised/VeRedact-2-revised.tex")
R = r"\textcolor{red}{%s}"
GONE = r"\textcolor{red}{\textsf{\footnotesize[%s: removed]}}"

ITEMS = [
    # A: cost tables / Phase 4 definition
    ("A1", r"$2T_V+T_{ZV}+T_S+T_{\mathrm{PRF}}$", None, R % r"$2T_V+T_{ZV}+2T_S+T_{\mathrm{PRF}}$"),
    ("A2", r"$|\Omega_e|(t\,T_{PA}+T_{CB}+T_{CH}+T_S)$", None, R % r"$t\,T_V+|\Omega_e|(t\,T_{PA}+T_{CB}+T_{CH}+T_S)$"),
    ("A3", r"& $|R|+|\sigma|+|\pi|$", None, "& " + R % r"$|R|+2|\sigma|+|\pi|$"),
    ("A4", r"=f(\lambda_e,|\mathcal{Q}_e|,T_{\max})", None, "=" + R % r"\lambda_e\,T_{\max}"),
    ("A5", "Consortium nodes,", "containers,", R % "The Besu validator nodes ran as Docker containers, while committee "
     "members, the VPS, and auditors ran as processes on the same host,"),
    ("A6a", r"~\cite{ref1,ref2,ref6,ref30}.", None, "~" + R % r"\cite{ref1,ref2,ref6}" + "."),
    ("A6b", r"~\cite{ref1,ref3,ref6,ref19,ref30}.", None, "~" + R % r"\cite{ref1,ref3,ref6,ref19}" + "."),
    # B: [TBD] values the code fixes
    ("B1", r"\textbf{[TBD]} lines of \textbf{[TBD: language]} code", None,
     R % "8,000 lines of Python, Rust, and Solidity code"),
    ("B2", r"STARK proof system \textbf{[TBD: library]},", None, "STARK proof system " + R %
     "(winterfell~0.13, Rescue-Prime credential registry, 42 queries, blowup 8, 16-bit grinding)" + ","),
    ("B3", r"\textbf{[TBD: confirm construction]}.", None,
     R % r"using a gadget-based lattice trapdoor with dealerless $t$-of-$n$ Shamir sharing of the trapdoor" + "."),
    ("B4", r"running Ubuntu \textbf{[TBD]}.", None, "running Ubuntu " + R % "24.04" + "."),
    # D: runs
    ("D1", "used, and all reported results represent the mean of 30 independent runs", r"with 95\% confidence intervals.",
     "used. " + R % r"Each configuration point is executed once; reported values are medians (and 95th percentiles "
     r"for latency) over all requests or samples of that run, with 95\% confidence intervals of the mean."),
    ("D2", r"Repetitions & 30 runs, 95\% confidence interval \\", None,
     R % "Runs" + " & " + R % r"1 per point; 30 samples per point (Exp.~2--4)" + r" \\"),
    # E: variants and second settings removed (bottom-up order does not matter: each find is unique)
    ("E1", r"and~\cite{ref34}. In addition, three internal variants isolate the", r"\end{enumerate}",
     r"and~\cite{ref34}." + GONE % "E1 variant list"),
    ("E2", r"Fig.~\ref{fig:exp1_redaction}(b) shows that at low arrival rates",
     "benefit of coalesced Merkle updates and shared PQCH adaptation.",
     R % (r"Fig.~\ref{fig:exp1_redaction}(b) shows that batched execution adds a waiting time at low arrival "
          r"rates, because a batch waits for additional requests; ABRRR bounds this wait by $T_{\max}$. Under "
          r"heavy workloads, ABRRR enlarges batches toward $B_{\max}$, improving amortization.")),
    ("E3", "define no separate authorization step. An internal",
     r"re-verify each PQZK proof instead of the VPS attestation $\alpha_i$.",
     "define no separate authorization step." + GONE % "E3 Re-ZK variant"),
    ("E4", "Re-ZK exhibits substantially higher latency because each batch requires",
     "without weakening request-level validation.", GONE % "E4 Re-ZK sentence"),
    ("E5", r"$n_Q\in\{10,10^2,10^3,10^4\}$, while the average number of returned", "control evidence sharing.",
     r"$n_Q\in\{10,10^2,10^3,10^4\}$, " + R % r"with records drawn from authorization batches of \textbf{[64]} requests."),
    ("E6", r"Scheme~\cite{ref13} and Scheme~\cite{ref1}. An internal variant,",
     "query-scoped multiproof with shared batch evidence.",
     r"Scheme~\cite{ref13} and Scheme~\cite{ref1}." + GONE % "E6 Per-Record variant"),
    ("E7", "Per-Record Evidence, which repeats complete authorization evidence for",
     "the multiproof continues to reduce redundant authentication paths.", GONE % "E7 Per-Record + clustering"),
    ("E8", r"Experiment~3 under two verification levels: \textbf{Normal Audit},",
     "validation attestations, state-transition and PQCH checks, and PQZK verification.",
     "Experiment~3 " + R % (r"for the \textbf{Normal Audit}, which verifies validation attestations and the "
     r"committed $H(\pi_i^{PQ})$. Verification time is decomposed into response signature and query binding, RAI "
     r"multiproof, committee approvals, validation attestations, and state-transition and PQCH checks.")),
    ("E9", "versus number of verified records for normal and deep audits and", None,
     "versus number of verified records for " + R % "the normal audit" + " and"),
    ("E10", r"approvals contribute only $t|\Omega_{Q_j}^B|T_V$. Deep-audit verification",
     "audits in which independent re-verification is required.",
     r"approvals contribute only $t|\Omega_{Q_j}^B|T_V$. " + R % ("Routine audits therefore rely only on PQ-signed "
     "attestations and hash-based authentication; complete PQZK verification is reserved for challenged or "
     "forensic audits.")),
    ("E11", r"under Zipf skews $s\in\{0,0.8\}$.", None, "under " + R % "Zipf skew $s=0.8$" + "."),
    ("E12", "shows that the amortized gas per redaction decreases as $m$ increases,",
     "redactions share each checkpoint update.",
     "shows that the amortized gas per redaction decreases as $m$ increases, " + R %
     "since more redactions share each checkpoint update."),
    # F: pilot finding
    ("F1", "threshold adaptation or policy-based authorization. VeRedact-PQ sustains the", None,
     "threshold adaptation or policy-based authorization. " + R % (r"Moreover, Ref.~\cite{ref1} permits only one "
     "redaction per block, so once every targeted block has been redacted, further requests are rejected and its "
     "throughput of finalized redactions falls to near zero.") + " VeRedact-PQ sustains the"),
]


def pat(s):  # whitespace in the find text matches any whitespace run (the .tex is hard-wrapped and indented)
    return r"\s+".join(re.escape(w) for w in s.split())


def main():
    tex = SRC.read_text()
    for iid, a, b, rep in ITEMS:
        rx = pat(a) + (r".*?" + pat(b) if b else "")
        hits = list(re.finditer(rx, tex, re.S))
        if len(hits) != 1:
            raise SystemExit(f"{iid}: find matched {len(hits)} times")
        m = hits[0]
        tex = tex[: m.start()] + rep + tex[m.end() :]
    # A6: the duplicate entry is KEPT (deleting it renumbers [31]-[38], so [34] would become [33]); marked instead
    tex = tex.replace(r"\bibitem{ref30}", r"\bibitem{ref30}\textcolor{red}{[A6: duplicate of [1]; no longer cited]} ", 1)
    pre = (r"\usepackage{xcolor}" "\n"
           r"\makeatletter\let\vr@ig\includegraphics" "\n"
           r"\renewcommand{\includegraphics}[2][]{\IfFileExists{#2}{\vr@ig[#1]{#2}}"
           r"{\fbox{\parbox[c][4cm][c]{0.75\linewidth}{\centering\ttfamily\small [figure: \detokenize{#2}]}}}}"
           r"\makeatother" "\n")
    tex = tex.replace(r"\begin{document}", pre + r"\begin{document}", 1)
    OUT.write_text(tex)
    print(f"{len(ITEMS)} items applied -> {OUT}")


if __name__ == "__main__":
    main()
