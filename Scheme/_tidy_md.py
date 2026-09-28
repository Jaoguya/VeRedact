"""Tidy marker-generated Markdown: join paragraph fragments, normalise headings, drop empty anchors.

Usage: python3 _tidy_md.py <file.md> [...]
"""
import re
import sys

EMPTY_SPAN = re.compile(r'<span id="[^"]*">\s*</span>\s*', re.S)
INLINE_MATH = re.compile(r"(?<![\$\\])\$(?!\$)[ \t]*(.+?)[ \t]*(?<![\$\\])\$(?!\$)")
STRUCTURAL = re.compile(r"^(#|\||>|!\[|\$\$|```|- |\d+\)\s|\*\*Output:\*\*)")


def heading(line, first):
    text = re.sub(r"^#+\s*", "", line).strip()
    text = re.sub(r"^\*+\s*(.*?)\s*\*+$", r"\1", text)  # *A. Contribution* -> A. Contribution
    text = re.sub(r"\s+", " ", text)
    if first:
        return "# " + text
    if re.match(r"^[IVX]+\.\s", text) or re.match(r"^(REFERENCES|ACKNOWLEDG(E)?MENT)$", text, re.I):
        return "## " + text
    if re.match(r"^[A-H]\.\s", text):
        return "### " + text
    return "#### " + text


def tidy(md):
    md = EMPTY_SPAN.sub("", md)
    lines = [l.rstrip() for l in md.split("\n")]
    out, para, in_code, seen_title = [], [], False, False

    def flush():
        if para:
            s = " ".join(p.strip() for p in para)
            s = re.sub(r"\s+([,.;:)])", r"\1", s)
            s = re.sub(r"\(\s+", "(", s)
            out.append(re.sub(r"[ \t]{2,}", " ", s))
            para.clear()

    for line in lines:
        if line.lstrip().startswith("```"):
            flush()
            in_code = not in_code
            out.append(line)
            continue
        if in_code:
            out.append(line)
            continue
        stripped = line.strip()
        if not stripped:
            flush()
            out.append("")
            continue
        if not stripped.startswith("|") and not stripped.startswith("$$"):
            stripped = INLINE_MATH.sub(lambda m: "$" + m.group(1) + "$", stripped)
        if stripped.startswith("#"):
            flush()
            out.append(heading(stripped, not seen_title))
            seen_title = True
            continue
        if stripped.startswith("|"):
            flush()
            cells = [INLINE_MATH.sub(lambda m: "$" + m.group(1) + "$", c.strip()) for c in stripped.strip("|").split("|")]
            out.append("| " + " | ".join(cells) + " |")
            continue
        if STRUCTURAL.match(stripped):
            flush()
        para.append(stripped)
    flush()

    text = "\n".join(out)
    text = re.sub(r"\n{3,}", "\n\n", text)
    # headings/tables/images need a blank line before them to render
    text = re.sub(r"([^\n])\n(#{1,4} |\| |!\[)", lambda m: m.group(1) + "\n\n" + m.group(2) if not (m.group(1) == "|" or m.group(2) == "| " and m.group(1).endswith("|")) else m.group(0), text)
    return text.strip() + "\n"


if __name__ == "__main__":
    for path in sys.argv[1:]:
        src = open(path).read()
        open(path, "w").write(tidy(src))
        print(f"tidied {path}: {len(src.splitlines())} -> {len(open(path).read().splitlines())} lines")
