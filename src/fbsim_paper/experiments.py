"""Explicit selection of analyses outside the nine-cell ICLR R&R instrument."""
import os

CONDITIONALS_ENV = "FBSIM_INCLUDE_MICROPOLIS_CONDITIONALS"


def include_micropolis_conditionals():
    """Standalone asset scripts default to the R&R even if extra inputs exist."""
    value = os.environ.get(CONDITIONALS_ENV, "0")
    if value not in ("0", "1"):
        raise ValueError(f"{CONDITIONALS_ENV} must be 0 or 1")
    return value == "1"
