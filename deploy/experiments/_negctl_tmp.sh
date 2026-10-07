#!/usr/bin/env bash
# negative control: the no-leftover-thread test must FAIL with the fix removed
cd /opt/veredact
rm -rf /tmp/negrepo && rsync -a --exclude .venv --exclude results --exclude target --exclude .cache ./ /tmp/negrepo/
.venv/bin/python - <<'P'
import pathlib
p=pathlib.Path("/tmp/negrepo/src/veredact_bench/evaluation/experiments/exp01_redaction_throughput.py"); s=p.read_text()
s=s.replace("if item is None or stop.is_set():","if item is None:").replace("if r is None or stop.is_set():","if r is None:").replace("    for th in clients + workers + workers_r:\n        th.join()\n","")
p.write_text(s)
P
cd /tmp/negrepo && timeout 600 env PYTHONPATH=/tmp/negrepo/src /opt/veredact/.venv/bin/python -m pytest -q -p no:cacheprovider -k no_thread_behind tests/test_results.py 2>&1 | grep -E "^E  |passed|failed" | head -4
echo NEG_DONE
rm -rf /tmp/negrepo
