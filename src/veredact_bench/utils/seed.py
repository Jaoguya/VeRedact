"""One place that seeds every random source the evaluation uses.

Covered: Python `random` (module-level) and NumPy's global generator. There is no PyTorch/CUDA here.
Components that need their own reproducible stream take the seed explicitly instead of sharing the global
state: the dataset and request trace (random.Random(meta.seed)), the PQCH DKG (seeded, cached), the STARK
credential registry. Protocol nonces, signature randomness and timestamps stay fresh on purpose (they
are part of what is measured), so timings vary between runs while data, trace and parameters do not.
"""
import os
import random

import numpy as np


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed % 2**32)
    os.environ["VRPQ_SEED"] = str(seed)  # recorded in run_info.json; child processes inherit it
