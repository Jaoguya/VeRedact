# VeRedact-PQ evaluation. One command per paper artifact; every run is gated by the config check.
# EVERYTHING RUNS ON THE AWS SERVER (author decision 2026-10-05: no local compute). On the laptop each target
# below is forwarded to veredact-bench by deploy/aws/remote.sh (paper/ is copied back); on the server the
# marker /opt/veredact/.on-server makes the same targets run directly.
#   make test lint                               tests, ruff gate
#   make smoke                                   every experiment on the smoke tier
#   make eval EXP=exp02_authorization_latency TIER=pilot      one experiment on one tier
#   make all TIER=experiment                     all experiments + tables + figures (server: deploy/aws/launch_run.sh)
#   make tables figures TIER=experiment          paper/tables/*.tex, paper/figures/*.pdf from results/
TIER ?= smoke
EXP  ?= all
PY   := .venv/bin/python
FORCE ?=
ON_SERVER := $(wildcard /opt/veredact/.on-server)

.PHONY: venv build-zk test lint validate eval smoke pilot experiment tables figures all capabilities paper-runs clean-results resummarize

ifeq ($(ON_SERVER),)
# laptop: forward every target to the server (same target, same variables)
venv build-zk test lint validate eval smoke pilot experiment tables figures all capabilities paper-runs resummarize:
	deploy/aws/remote.sh make $@ TIER=$(TIER) EXP=$(EXP) FORCE=$(FORCE)
clean-results:
	@echo "results/ lives on the server; delete there via: deploy/aws/remote.sh make clean-results"
else

venv:
	python3.12 -m venv .venv
	$(PY) -m pip install -q -U pip
	$(PY) -m pip install -q -e '.[dev]'

build-zk:                        ## winterfell STARK -> vrpq_stark module (needs Rust: rustup or brew install rust)
	cd native/pqzk_stark && ../../.venv/bin/maturin develop --release -q

test:
	$(PY) -m pytest -q

lint:                            ## quality gate: ruff lint + format check (config in pyproject.toml)
	.venv/bin/ruff check src tests scripts tools deploy/aws/aws_config.py
	.venv/bin/ruff format --check src tests scripts tools deploy/aws/aws_config.py

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

resummarize:                     ## metrics.json from stored rows after a metric-DEFINITION change (EXP=..., TIER=...)
	$(PY) scripts/resummarize.py --tier $(TIER) --experiment $(EXP)

clean-results:                   ## deletes results/ on this machine (keeps the folder marker)
	find results -mindepth 1 ! -name .keep-results -exec rm -rf {} +
endif
