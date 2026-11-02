# Sourced by provision_workers.sh and provision_provers.sh. Long steps run DETACHED on the host and the laptop only
# polls, with retries: a dropped SSH session (laptop asleep, lid closed, new IP) pauses the polling, never the work
# (full run 2026-11-01: the prover bootstrap died twice with the laptop's SSH session).

retry() {   # retry <command...>: up to 40 tries, 15 s apart (~10 min of laptop sleep or network loss)
  local i
  for i in $(seq 1 40); do "$@" && return 0; sleep 15; done
  return 1
}

# detached_bootstrap <log file> <minutes> <ssh...>: run /tmp/bootstrap_server.sh as root on the host in its own
# session (env from BOOT_ENV), wait for its exit code up to <minutes> of wall time, copy its log to <log file>.
detached_bootstrap() {
  local log=$1 mins=$2 rc="" end; shift 2
  retry "$@" "sudo rm -f /var/tmp/veredact-boot.rc; (sudo env $BOOT_ENV setsid nohup bash -c \
    'bash /tmp/bootstrap_server.sh > /var/tmp/veredact-boot.log 2>&1; echo \$? > /var/tmp/veredact-boot.rc' \
    < /dev/null > /dev/null 2>&1 &)" || return 1
  end=$(( $(date +%s) + mins * 60 ))
  while [[ -z "$rc" && $(date +%s) -lt $end ]]; do
    sleep 20
    rc=$("$@" "cat /var/tmp/veredact-boot.rc 2>/dev/null" 2>/dev/null || true)
  done
  retry "$@" "cat /var/tmp/veredact-boot.log" > "$log" 2>&1 || true
  [[ "$rc" == 0 ]]
}

# wait_until <minutes> <ssh...> -- <remote test>: true once the remote test succeeds (wall-clock deadline)
wait_until() {
  local mins=$1 end; shift
  local -a ssh=(); while [[ $1 != -- ]]; do ssh+=("$1"); shift; done; shift
  end=$(( $(date +%s) + mins * 60 ))
  while [[ $(date +%s) -lt $end ]]; do "${ssh[@]}" "$*" 2>/dev/null && return 0; sleep 10; done
  return 1
}
