"""Print the capability matrix reported by each method's implementation (Scheme.capabilities())."""

from veredact_bench.methods.registry import capability_matrix
from veredact_bench.utils.config import load

if __name__ == "__main__":
    print(capability_matrix(load("smoke")))
