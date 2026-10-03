"""Experiment runners. Each exposes run(cfg, out: RunWriter); names follow operations every system performs.
primitives = the per-operation timing table (tab:primitives); exp1..exp5 = the manuscript's Experiments 1-5."""
from . import exp1, exp2, exp3, exp4, exp5, primitives

ALL = {"primitives": primitives.run, "exp1": exp1.run, "exp2": exp2.run, "exp3": exp3.run, "exp4": exp4.run,
       "exp5": exp5.run}
