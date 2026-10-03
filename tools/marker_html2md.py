"""Convert marker HTML output to Markdown with marker's own converter, and report completeness.

Run with the marker venv: ~/.venvs/marker/bin/python tools/marker_html2md.py <p.html> <reference.md|/dev/null>
Writes <p.md> next to the HTML. Used by tools/marker_convert.sh.
"""

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup
from marker.renderers.markdown import MarkdownRenderer, cleanup_text

html_path, ref_md = Path(sys.argv[1]), Path(sys.argv[2])
html = html_path.read_text()
md = cleanup_text(MarkdownRenderer().md_cls.convert(html))
html_path.with_suffix(".md").write_text(md)


def words(text):
    return len(re.findall(r"[A-Za-z]{3,}", text))


html_words = words(BeautifulSoup(html, "html.parser").get_text(" "))
print(
    f"{html_path.stem}: html={html_words} md={words(md)} "
    f"reference={words(ref_md.read_text()) if ref_md.is_file() else '-'} (alphabetic words >=3 letters)"
)
