# VeRedact-PQ evaluation. One command per paper artifact; every run is gated by the config check.
#   make venv build-zk test                      one-time setup (Python 3.12 + Rust) and tests
#   make smoke                                   every experiment on the smoke tier (laptop, minutes)
#   make eval EXP=exp02_authorization_latency TIER=pilot      one experiment on one tier
#   make all TIER=experiment                     all experiments + tables + figures (server: deploy/aws/launch_run.sh)
#   make tables figures TIER=experiment          paper/tables/*.tex, paper/figures/*.pdf from results/
TIER ?= smoke
EXP  ?= all
PY   := .venv/bin/python
FORCE ?=

.PHONY: venv build-zk test validate eval smoke pilot experiment tables figures all capabilities paper-runs clean-results

venv:
	python3.12 -m venv .venv
	$(PY) -m pip install -q -U pip
	$(PY) -m pip install -q -e '.[dev]'

build-zk:                        ## winterfell STARK -> vrpq_stark module (needs Rust: rustup or brew install rust)
	cd native/pqzk_stark && ../../.venv/bin/maturin develop --release -q

test:
	$(PY) -m pytest -q

validate:
	$(PY) scripts/validate_config.py $(TIER)

eval: validate                   ## results/<exp>/<method>/<TIER>/ (finished methods skipped; FORCE=--force re-runs)
	$(PY) scripts/run_eval.py --tier $(TIER) --experiment $(EXP) $(FORCE)

smoke:
	$(MAKE) eval TIER=smoke EXP=all

pilot experiment:                ## on the server, with Besu: deploy/experiments/run_experiments.sh
	deploy/experiments/run_experiments.sh $@ all

tables:
	$(PY) scripts/make_tables.py --tier $(TIER)

figures:
	$(PY) scripts/make_figures.py --tier $(TIER)

all: eval tables figures

capabilities:
	$(PY) scripts/capabilities.py

paper-runs:                      ## each baseline's OWN paper evaluation (original instantiation), quick
	$(PY) scripts/paper_reproduction.py all --quick

clean-results:                   ## deletes local results/ (keeps the folder marker)
	find results -mindepth 1 ! -name .keep-results -exec rm -rf {} +
