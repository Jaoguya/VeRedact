"""Fast fallback: pdftotext -> readable Markdown (math/tables flattened). Prefer tools/marker_convert.sh.

Usage: python3 tools/pdf2md_pdftotext.py <dir_with_pdfs> <out_dir>
"""

import re
import subprocess
import sys
from pathlib import Path

DROP = [
    r"^Authorized licensed use limited to",
    r"IEEE (TRANSACTIONS|INTERNET OF THINGS JOURNAL)[^.]*VOL\.",
    r"^[A-Z .]+ et al\.: [A-Z]",  # running header, e.g. "LI et al.: REDACTABLE ..."
    r"^\d{3,5}$",  # page numbers
    r"©\s?20\d\d IEEE",
    r"^Personal use is permitted",
    r"^See https://www\.ieee\.org/publications",
    r"^and similar technologies\. Personal use",
    r"^\d{4}-\d{3}[\dX]/\d\d/\$31\.00",
    r"^2025 IEEE 24th International Conference on Trust",
    r"^DOI 10\.1109/Trustcom",
]
DROP_RE = [re.compile(p) for p in DROP]
H1 = re.compile(r"^([IVX]+)\.\s+([A-Z][A-Z .,\-’'&]+)$")  # I. INTRODUCTION
H2 = re.compile(r"^([A-H])\.\s+([A-Z][A-Za-z ,\-’'&():]{2,80})$")  # A. Contribution
REFS = re.compile(r"^R\s?EFERENCES$|^REFERENCES$")
REF_ITEM = re.compile(r"^\[\d+\]\s")


def fix_spaced_caps(s):
    # "I NTRODUCTION" / "R ELATED W ORK" -> "INTRODUCTION" / "RELATED WORK"
    return re.sub(r"(?<![’'\w])([A-Z]) ([A-Z]{2,})\b", r"\1\2", s)


ACRONYMS = {"Dch": "DCH", "Rebs": "REBS", "Etch": "ETCH", "Et": "et", "Al.’S": "al.’s", "Al.'S": "al.'s"}


def fix_case(h):
    small = {"Of", "And", "The", "In", "For", "On", "With", "To"}
    words = h.title().split()
    out = [ACRONYMS.get(w, w) for w in words]
    return " ".join(w.lower() if i and w in small else w for i, w in enumerate(out))


def pdftotext(pdf, *args):
    return subprocess.run(["pdftotext", *args, str(pdf), "-"], capture_output=True, text=True).stdout


def extract_by_columns(pdf, title_h=250):
    """Read each page as left column then right column (for PDFs whose reading order is scrambled)."""
    info = subprocess.run(["pdfinfo", str(pdf)], capture_output=True, text=True).stdout
    pages = int(re.search(r"Pages:\s+(\d+)", info).group(1))
    w, h = map(float, re.search(r"Page size:\s+([\d.]+) x ([\d.]+)", info).groups())
    half, parts = int(w / 2), []
    for pg in range(1, pages + 1):
        top = title_h if pg == 1 else 0
        crop = lambda x, y, W, H: pdftotext(
            pdf, "-f", str(pg), "-l", str(pg), "-x", str(x), "-y", str(y), "-W", str(W), "-H", str(H)
        )
        if top:
            parts.append(crop(0, 0, int(w), top))
        parts.append(crop(0, top, half, int(h) - top))
        parts.append(crop(half, top, int(w) - half, int(h) - top))
    return "\n\n".join(parts)


COLUMN_MODE = ("Efficient_Auditing",)


def convert(pdf: Path, out: Path):
    if pdf.name.startswith(COLUMN_MODE):
        raw = extract_by_columns(pdf)
    else:
        raw = pdftotext(pdf)
    raw = raw.replace("\f", "\n\n")
    lines = [l.rstrip() for l in raw.splitlines()]
    lines = [l for l in lines if not any(r.search(l.strip()) for r in DROP_RE)]

    blocks, cur = [], []
    for l in lines:
        s = l.strip()
        if not s:
            if cur:
                blocks.append(cur)
                cur = []
            continue
        cur.append(s)
    if cur:
        blocks.append(cur)

    # drop caps: pdftotext may emit the big initial letter a few blocks before/after its word
    for i, b in enumerate(blocks):
        for k, line in enumerate(b):
            m = re.match(r"^([A-Z]{3,})\s+[a-z]", line)
            if not m:
                continue
            for j in range(max(0, i - 3), min(len(blocks), i + 4)):
                if j != i and len(blocks[j]) == 1 and re.fullmatch(r"[A-Z]", blocks[j][0]):
                    w = m.group(1)
                    b[k] = blocks[j][0] + w.lower() + line[len(w) :]
                    blocks[j] = []
                    break
            break
    blocks = [b for b in blocks if b]

    md, in_refs, h1_open, pending_h1, drop = [], False, False, "", ""
    for b in blocks:
        if len(b) == 1 and re.fullmatch(r"[A-Z]", b[0]):
            drop = b[0]  # drop-cap letter, glue to next paragraph
            continue
        if drop and re.match(r"^[A-Z]{2,}", b[0]):
            w = re.match(r"^[A-Z]+", b[0]).group(0)
            b = [drop + w.lower() + b[0][len(w) :]] + b[1:]
            drop = ""
        text = ""
        for s in b:
            s = s2 = fix_spaced_caps(s)
            if H1.match(s2) or REFS.match(s2):
                if text:
                    md.append(text)
                    text = ""
                if REFS.match(s2):
                    in_refs = True
                    md.append("## References")
                else:
                    m = H1.match(s2)
                    num, pending_h1 = m.group(1), m.group(2)
                    md.append(f"## {num}. " + fix_case(pending_h1))
                    h1_open = True
                continue
            if h1_open and re.fullmatch(r"[A-Z][A-Z ,\-’'&]+", s2):
                pending_h1 += " " + s2
                md[-1] = f"## {num}. " + fix_case(pending_h1)
                continue
            h1_open = False
            if H2.match(s) and len(s) < 70 and not in_refs:
                if text:
                    md.append(text)
                    text = ""
                md.append(f"### {s}")
                continue
            if re.match(r"^(r [A-Z]|• )", s):  # bullet glyphs from pdftotext
                if text:
                    md.append(text)
                md_line = "- " + s[2:]
                text = md_line
                continue
            if in_refs and REF_ITEM.match(s) and text:
                md.append(text)
                text = s
                continue
            if not text:
                text = s
            elif text.endswith("-") and not text.endswith(" -"):
                text = text[:-1] + s
            else:
                text += " " + s
        if text:
            md.append(text)

    # "REFERENCES" heading can be emitted before trailing sections; move it to the first [1] entry
    if "## References" in md:
        r = md.index("## References")
        first = next((i for i, x in enumerate(md) if x.startswith("[1] ")), None)
        if first and first > r + 1 and any(x.startswith("## ") for x in md[r + 1 : first]):
            md.pop(r)
            md.insert(first - 1, "## References")
    # drop-cap that pdftotext splits as "B" ... "LOCKCHAIN"
    md = [re.sub(r"^LOCKCHAIN ", "Blockchain ", x) for x in md]

    title = pdf.stem.replace("_", " ")
    header = (
        f"# {title}\n\n"
        f"> Full text extracted from `{pdf.name}` with `pdftotext`. "
        "Equations, tables and figures embedded as images or complex layout may be garbled or missing; "
        "check the PDF for those.\n"
    )
    out.write_text(header + "\n" + "\n\n".join(md) + "\n")


if __name__ == "__main__":
    src, dst = Path(sys.argv[1]), Path(sys.argv[2])
    dst.mkdir(parents=True, exist_ok=True)
    for pdf in sorted(src.glob("*.pdf")):
        convert(pdf, dst / (pdf.stem + ".md"))
        print("wrote", dst / (pdf.stem + ".md"))
