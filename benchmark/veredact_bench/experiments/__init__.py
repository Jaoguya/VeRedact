"""Exp. 1-5 runners. Each exposes run(cfg, out: RunWriter); names follow operations every system performs."""
from . import exp1, exp2, exp3, exp4, exp5

ALL = {"exp1": exp1.run, "exp2": exp2.run, "exp3": exp3.run, "exp4": exp4.run, "exp5": exp5.run}
