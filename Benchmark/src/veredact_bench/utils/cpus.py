"""CPU partition for Exp. 1 (audit A3): requester processes on their own physical cores, the system under
test (VPS workers, executor, Besu validators) on the rest — as if requesters proved on their own machines."""

import glob
import os
import subprocess
from collections import defaultdict
from pathlib import Path


def physical_cores() -> list[list[int]]:
    """[[cpu ids of one physical core], ...] from sysfs (Linux); [] elsewhere."""
    cores = defaultdict(list)
    for d in glob.glob("/sys/devices/system/cpu/cpu[0-9]*/topology"):
        cpu = int(d.split("/cpu")[-1].split("/")[0])
        key = (Path(d, "physical_package_id").read_text().strip(), Path(d, "core_id").read_text().strip())
        cores[key].append(cpu)
    return [sorted(v) for _, v in sorted(cores.items())]


def split(requester_cores: int):
    """(requester cpus, system cpus): the first requester_cores physical cores (both hyperthreads) for the
    requesters, the rest for the system. (None, None) when off (0) or not on Linux."""
    cores = physical_cores()
    if requester_cores <= 0 or not cores or not hasattr(os, "sched_setaffinity"):
        return None, None
    if requester_cores >= len(cores):
        raise ValueError(f"requester_cores={requester_cores} leaves no core for the system ({len(cores)} cores)")
    return sum(cores[:requester_cores], []), sum(cores[requester_cores:], [])


def pin_besu(cpus) -> None:
    """Restrict the Besu validator containers to cpus (None: every cpu)."""
    allcpus = sum(physical_cores(), [])
    target = ",".join(map(str, sorted(cpus if cpus else allcpus)))
    names = subprocess.run(["docker", "ps", "--format", "{{.Names}}"], capture_output=True, text=True).stdout.split()
    for n in (n for n in names if n.startswith("besu-validator")):
        subprocess.run(["docker", "update", "--cpuset-cpus", target, n], check=True, capture_output=True)
