# VeRedact-PQ evaluation. Every experiment target depends on validate-config: an invalid config cannot run.
#   make venv build-zk test            one-time local setup + unit/fidelity tests
#   make smoke                         all experiments, config/smoke.toml (laptop, minutes)
#   make pilot | make experiments      pilot / paper tier (server: deploy/aws/launch_run.sh)
#   make exp1 CONFIG=config/pilot.toml one experiment on any tier
#   make capabilities plots            capability matrix from the code; figures from the newest runs
CONFIG ?= config/smoke.toml
PY     := benchmark/.venv/bin/python

.PHONY: venv build-zk validate-config test fidelity-check smoke pilot experiments \
        exp1 exp2 exp3 exp4 exp5 capabilities plots paper-runs clean-results

venv:
	python3.12 -m venv benchmark/.venv
	$(PY) -m pip install -q -U pip
	$(PY) -m pip install -q -r benchmark/requirements.txt
	$(PY) -m pip install -q -e benchmark

build-zk:                        ## winterfell STARK -> vrpq_stark module (needs Rust: rustup or brew install rust)
	cd benchmark/pqzk_stark && ../.venv/bin/maturin develop --release -q

validate-config:
	$(PY) -m veredact_bench.validate_config $(CONFIG)

test:
	cd benchmark && .venv/bin/python -m pytest -q tests
	$(PY) -m pytest -q -p no:cacheprovider experiment

fidelity-check:                  ## negative tests: each system rejects exactly what its paper can reject
	cd benchmark && .venv/bin/python -m pytest -q tests/test_fidelity.py

exp1 exp2 exp3 exp4 exp5: validate-config
	$(PY) -m veredact_bench run $@ --config $(CONFIG)

smoke:
	$(MAKE) validate-config CONFIG=config/smoke.toml
	$(PY) -m veredact_bench run all --config config/smoke.toml

pilot:
	deploy/experiments/run_experiments.sh pilot all

experiments:
	deploy/experiments/run_experiments.sh experiment all

capabilities:
	$(PY) -m veredact_bench capabilities --config $(CONFIG)

plots:
	$(PY) -m veredact_bench.plot

paper-runs:                      ## each baseline's OWN paper evaluation (original instantiation), --quick
	for s in S1_ImprovedDCH/s1 S13_EAQVRBC/s13 S27_ETCH/s27 S34_REBS/s34; do $(PY) experiment/$${s}_run.py --quick; done

clean-results:                   ## deletes local results/ runs (keeps the directory marker)
	find results -mindepth 1 ! -name .keep-results -exec rm -rf {} +
