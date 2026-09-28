#!/bin/zsh
# Convert one scheme PDF to Markdown full text with marker (LaTeX math/tables) and place it in Scheme/.
#
# Usage: tools/marker_convert.sh <paper.pdf> <Scheme/S<ref>_<Author><Year>_<Short>> <S<ref>>
# Example: tools/marker_convert.sh ~/Downloads/wang.pdf Scheme/S17_Wang2024_QRTU S17
#
# Output in the scheme folder:
#   <pdf>                    original (renamed only if it would collide)
#   S<ref>_fulltext.md         marker full text, tidied
#   S<ref>_figures/            figures extracted by marker
# Afterwards: write S<ref>_summary.md, add [schemes.S<ref>] to config/schemes.toml (see SKILL.md).
#
# Needs: ~/.venvs/marker (pip install marker-pdf) with the local auto-close patch, and llama.cpp
# (brew install llama.cpp). ~10 pages take ~25-30 min on an 8 GB Apple-silicon Mac.
set -euo pipefail
pdf=$1; dest=$2; sid=$3
root=${0:A:h:h}
work=$(mktemp -d)
mkdir -p "$dest"
cp "$pdf" "$work/p.pdf"                       # short name: avoids long-path failures
export SURYA_INFERENCE_BACKEND=llamacpp SURYA_INFERENCE_PARALLEL=1 HF_HUB_DISABLE_SYMLINKS_WARNING=1
~/.venvs/marker/bin/marker_single "$work/p.pdf" --output_dir "$work/out" --mode balanced --output_format html
~/.venvs/marker/bin/python "$root/tools/marker_html2md.py" "$work/out/p/p.html" /dev/null || true
mkdir -p "$dest/${sid}_figures"
for f in "$work"/out/p/_page_*.jpeg(N); do    # prefix with S<ref> so figure names never collide across schemes
  cp "$f" "$dest/${sid}_figures/${sid}${f:t}"
done
sed "s#](\(_page_[^)]*\))#](${sid}_figures/${sid}\1)#g" "$work/out/p/p.md" > "$dest/${sid}_fulltext.md"
python3 "$root/tools/tidy_marker_md.py" "$dest/${sid}_fulltext.md"
[ -f "$dest/$(basename "$pdf")" ] || cp "$pdf" "$dest/"
pkill -f llama-server || true
echo "done: $dest/${sid}_fulltext.md — check tables/algorithms against the PDF (VLM output can be garbled)"
