"""Convert VeRedact.tex to VeRedact.md.

Revision colours: purple = superseded text (dropped), blue/red = current text (kept, colour removed).
Tables, authors, abstract, algorithm and bibliography are converted here; the rest goes through pandoc.

Usage: python3 tools/tex2md.py overleaf/VeRedact.tex overleaf/VeRedact.md
"""
import re
import subprocess
import sys


# ---------------------------------------------------------------- helpers
def match_brace(s, i):
    """s[i] == '{'; return index of the matching '}'."""
    depth = 0
    j = i
    while j < len(s):
        c = s[j]
        if c == "\\":
            j += 2
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return j
        j += 1
    raise ValueError(f"unbalanced brace at {i}")


def arg(s, cmd):
    """Content of the first {...} argument of \\cmd in s (balanced), or None."""
    i = s.find("\\" + cmd + "{")
    if i < 0:
        return None
    k = i + len(cmd) + 1
    return s[k + 1:match_brace(s, k)]


def replace_cmd(s, cmd, fn):
    """Replace every \\cmd{arg} by fn(arg), with balanced braces."""
    tok = "\\" + cmd + "{"
    out, pos = [], 0
    while (i := s.find(tok, pos)) >= 0:
        j = match_brace(s, i + len(tok) - 1)
        out.append(s[pos:i] + fn(s[i + len(tok):j]))
        pos = j + 1
    return "".join(out) + s[pos:]


def strip_colour(s, colour, keep):
    s = replace_cmd(s, "textcolor{%s}" % colour, lambda a: a if keep else "")
    tok = "{\\color{%s}" % colour
    while (i := s.find(tok)) >= 0:
        j = match_brace(s, i)
        s = s[:i] + (s[i + len(tok):j] if keep else "") + s[j + 1:]
    return s


def cite(keys):
    return "[" + ", ".join(k.strip().replace("ref", "") for k in keys.split(",")) + "]"


def inline(s):
    """Light LaTeX -> Markdown for table cells, bib entries, front matter."""
    s = re.sub(r"~?\\cite\{([^}]*)\}", lambda m: " " + cite(m.group(1)), s)
    s = replace_cmd(s, "makecell", lambda a: a.replace("\\\\", " "))
    s = replace_cmd(s, "textbf", lambda a: "**" + a.strip() + "**")
    s = replace_cmd(s, "emph", lambda a: "*" + a.strip() + "*")
    s = replace_cmd(s, "textit", lambda a: "*" + a.strip() + "*")
    s = replace_cmd(s, "texttt", lambda a: "`" + a.strip() + "`")
    s = re.sub(r"\$\\checkmark\$|\\checkmark", "✓", s)
    s = re.sub(r"\$\\times\$", "✗", s)
    s = re.sub(r"\$\\triangle\$", "△", s)
    s = re.sub(r"\\(footnotesize|scriptsize|small|centering)\b", "", s)
    s = s.replace("``", "“").replace("''", "”").replace("---", "—").replace("--", "–")
    s = s.replace("\\&", "&").replace("\\%", "%").replace("~", " ").replace("\\,", " ")
    s = s.replace("{,}", ",")
    return re.sub(r"\s+", " ", s).strip()


LABELS = {}

# ---------------------------------------------------------------- tables
def cell_md(c):
    """Inline-convert a table cell; '|' inside math would split the Markdown column."""
    return re.sub(r"\$[^$]*\$", lambda m: m.group(0).replace("|", "\\vert "), inline(c))


def tabular_to_md(body):
    body = replace_cmd(body, "makecell", lambda a: a.replace("\\\\", " "))
    segs = re.split(r"\\(?:hline|toprule|midrule|bottomrule)", body)
    parsed, notes = [], []
    for seg in segs:
        rows = []
        for r in re.split(r"\\\\(?![a-zA-Z])", seg):
            r = r.strip()
            if not r:
                continue
            m = re.match(r"\\multicolumn\{\d+\}\{(?:[^{}]|\{[^{}]*\})*\}\{(.*)\}\s*$", r, re.S)
            if m:
                notes.append(inline(m.group(1)))
            else:
                rows.append([cell_md(c) for c in re.split(r"(?<!\\)&", r)])
        if rows:
            parsed.append(rows)
    if len(parsed) > 1:
        header_rows, data_rows = parsed[0], [r for seg in parsed[1:] for r in seg]
    else:
        header_rows, data_rows = parsed[0][:1], parsed[0][1:]
    ncol = max(len(r) for r in header_rows + data_rows)
    header = [" ".join(filter(None, (r[c] if c < len(r) else "" for r in header_rows))) for c in range(ncol)]
    lines = ["| " + " | ".join(header) + " |", "|" + "|".join([":--"] * ncol) + "|"]
    for r in data_rows:
        lines.append("| " + " | ".join(r + [""] * (ncol - len(r))) + " |")
    return "\n".join(lines), notes


def convert_tables(tex, store):
    def repl(m):
        env = m.group(0)
        cap = arg(env, "caption") or ""
        body = re.search(r"\\begin\{tabular\}\{[^\n]*?\}\n(.*?)\\end\{tabular\}", env, re.S).group(1)
        table, notes = tabular_to_md(body)
        k = len(store)
        lab = re.search(r"\\label\{([^}]*)\}", env)
        if lab:
            LABELS[lab.group(1)] = roman(k + 1)
        md = f"**TABLE {roman(k + 1)}.** {inline(cap)}\n\n{table}"
        if notes:
            md += "\n\n" + "\n".join(f"*{n}*" for n in notes)
        store.append(md)
        return f"\n\nTABLEPLACEHOLDER{k}\n\n"

    return re.sub(r"\\begin\{table\*?\}.*?\\end\{table\*?\}", repl, tex, flags=re.S)


def roman(n):
    vals = [(10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")]
    out = ""
    for v, r in vals:
        while n >= v:
            out, n = out + r, n - v
    return out


# ---------------------------------------------------------------- algorithm
def algorithmic_to_text(body):
    out, indent = [], 0
    rules = [
        (r"\\Require\s*(.*)", "Require: {0}", 0, 0),
        (r"\\Ensure\s*(.*)", "Ensure: {0}", 0, 0),
        (r"\\ForAll\{(.*)\}\s*$", "for all {0} do", 0, 1),
        (r"\\For\{(.*)\}\s*$", "for {0} do", 0, 1),
        (r"\\If\{(.*)\}\s*$", "if {0} then", 0, 1),
        (r"\\Else\s*$", "else", -1, 1),
        (r"\\EndFor\s*$", "end for", -1, 0),
        (r"\\EndIf\s*$", "end if", -1, 0),
        (r"\\State\s*(.*)", "{0}", 0, 0),
        (r"\\Statex\s*(.*)", "    {0}", 0, 0),
    ]
    for raw in body.split("\n"):
        line = raw.strip()
        if not line:
            continue
        for pat, fmt, pre, post in rules:
            m = re.match(pat, line)
            if m:
                indent += pre
                out.append("    " * indent + fmt.format(*m.groups()))
                indent += post
                break
        else:
            out[-1] += " " + line
    text = "\n".join(out)
    text = replace_cmd(text, "textbf", lambda a: a)
    text = replace_cmd(text, "mathsf", lambda a: a)
    text = replace_cmd(text, "mathcal", lambda a: a)
    text = replace_cmd(text, "mathrm", lambda a: a)
    text = replace_cmd(text, "hspace", lambda a: "")
    for a, b in [("$", ""), ("\\gets", "←"), ("\\leftarrow", "←"), ("\\neq", "≠"), ("\\emptyset", "∅"),
                 ("\\parallel", "‖"), ("\\in", "∈"), ("\\Omega", "Ω"), ("\\delta", "δ"), ("\\{", "{"),
                 ("\\}", "}"), ("\\mathbf", ""), ("^{*}", "*"), ("_{", "_{")]:
        text = text.replace(a, b)
    return text


# ---------------------------------------------------------------- main passes
def preprocess(tex, tables):
    tex = re.sub(r"(?m)^\s*%.*$", "", tex)
    tex = re.sub(r"(?<!\\)%.*", "", tex)
    tex = re.sub(r"\\section\{Evaluation\} skeleton in VedRedact\.tex\)\s*", "", tex)  # stray duplicate

    tex = strip_colour(tex, "purple", keep=False)
    for c in ("blue", "red"):
        tex = strip_colour(tex, c, keep=True)
    tex = re.sub(r"\\color\{(blue|red)\}", "", tex)
    tex = re.sub(r"\\begin\{equation\}\s*\\end\{equation\}", "", tex)

    n = 0

    def number(m):
        nonlocal n
        n += 1
        lab = re.search(r"\\label\{([^}]*)\}", m.group(1))
        if lab:
            LABELS[lab.group(1)] = "(%d)" % n
        body = re.sub(r"\\label\{[^}]*\}", "", m.group(1)).strip()
        return "\\begin{equation*}\n" + body + "\n\\tag{%d}\n\\end{equation*}" % n

    tex = re.sub(r"\\begin\{equation\}(.*?)\\end\{equation\}", number, tex, flags=re.S)

    tex = convert_tables(tex, tables)

    figs = []

    def fig(m):
        env = m.group(0)
        cap = inline(arg(env, "caption") or "")
        src = re.search(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]*)\}", env).group(1).replace(" ", "%20")
        lab = re.search(r"\\label\{([^}]*)\}", env)
        k = len(figs) + 1
        if lab:
            LABELS[lab.group(1)] = str(k)
        figs.append(f"![Fig. {k}]({src})\n\n**Fig. {k}.** {cap}")
        tables.append(figs[-1])
        return f"\n\nTABLEPLACEHOLDER{len(tables) - 1}\n\n"

    tex = re.sub(r"\\begin\{figure\*?\}.*?\\end\{figure\*?\}", fig, tex, flags=re.S)
    LABELS.update({"alg:redaction": "1", "sec:security": "IV"})
    tex = re.sub(r"\\eqref\{([^}]*)\}", lambda m: LABELS.get(m.group(1), "(?)"), tex)
    tex = re.sub(r"\\(?:ref|Cref|cref)\{([^}]*)\}", lambda m: LABELS.get(m.group(1), "?"), tex)
    tex = re.sub(r"~?\\cite\{([^}]*)\}", lambda m: " " + cite(m.group(1)), tex)

    def alg(m):
        cap = arg(m.group(0), "caption") or ""
        body = re.search(r"\\begin\{algorithmic\}\[1\](.*?)\\end\{algorithmic\}", m.group(0), re.S).group(1)
        return "\n\\textbf{Algorithm 1: %s}\n\n\\begin{verbatim}\n%s\n\\end{verbatim}\n" % (
            re.sub(r"\s+", " ", cap), algorithmic_to_text(body))

    tex = re.sub(r"\\begin\{algorithm\}.*?\\end\{algorithm\}", alg, tex, flags=re.S)
    tex = re.sub(r"\\begin\{abstract\}", r"\\section{Abstract}", tex).replace("\\end{abstract}", "")
    tex = re.sub(r"\\begin\{IEEEkeywords\}(.*?)\\end\{IEEEkeywords\}",
                 lambda m: "\\textbf{Index Terms} --- " + m.group(1).strip(), tex, flags=re.S)
    tex = re.sub(r"\\subsubsection\*\{\\textbf\{(.*?)\}\}",
                 lambda m: "\\subsubsection{" + re.sub(r"\s+", " ", m.group(1)) + "}", tex, flags=re.S)
    tex = replace_cmd(tex, "makecell", lambda a: a.replace("\\\\", " "))
    return tex


def front_matter(doc):
    title = re.sub(r"\s+", " ", arg(doc, "title"))
    author = arg(doc, "author")
    names = inline(arg(author, "IEEEauthorblockN").replace("\\\\", ""))
    aff = arg(author, "IEEEauthorblockA").split("\\\\")
    return f"# {title}\n\n**{names}**\n\n{inline(aff[0])}  \n{inline(' '.join(aff[1:]))}\n"


def bibliography(doc):
    bib = doc.split("\\begin{thebibliography}", 1)[1].split("\\end{thebibliography}", 1)[0]
    items = re.split(r"\\bibitem\{ref(\d+)\}", bib)[1:]
    lines = ["## References", ""]
    for num, text in zip(items[0::2], items[1::2]):
        lines.append(f"[{num}] {inline(text)}")
        lines.append("")
    return "\n".join(lines)


def postprocess(md, tables):
    md = re.sub(r"(?m)^(#+) ", r"#\1 ", md)  # \section -> ##, \subsection -> ###, ...
    for k in reversed(range(len(tables))):  # reversed: PLACEHOLDER1 is a prefix of PLACEHOLDER10
        md = md.replace(f"TABLEPLACEHOLDER{k}", tables[k])
    md = md.replace("\\[", "[").replace("\\]", "]")
    md = re.sub(r"\s*\$\$\\begin\{equation\*\}\s*(.*?)\s*\\end\{equation\*\}\$\$\s*",
                lambda m: "\n\n$$\n" + m.group(1).strip() + "\n$$\n\n", md, flags=re.S)
    md = re.sub(r"\n{3,}", "\n\n", md)
    return md.strip() + "\n"


if __name__ == "__main__":
    src, dst = sys.argv[1], sys.argv[2]
    full = open(src).read()
    doc = full.split("\\begin{document}", 1)[1].split("\\end{document}", 1)[0]
    body = doc.split("\\maketitle", 1)[1].split("\\begin{thebibliography}", 1)[0]
    tables = []
    pre = "\\documentclass{article}\n\\begin{document}\n" + preprocess(body, tables) + "\n\\end{document}\n"
    md = subprocess.run(
        ["pandoc", "-f", "latex", "-t", "gfm-tex_math_gfm+tex_math_dollars", "--wrap=none"],
        input=pre, capture_output=True, text=True, check=True,
    ).stdout
    out = front_matter(doc) + "\n" + postprocess(md, tables) + "\n" + bibliography(doc)
    open(dst, "w").write(out)
    print(f"wrote {dst}: {len(tables)} tables+figures, {out.count(chr(92) + 'tag{')} numbered equations")
