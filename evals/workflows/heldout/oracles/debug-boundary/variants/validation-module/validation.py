"""Boundary checks for POST /readings batches."""
import math


def readings_error(readings):
    """Name the contract violation in readings, or return None."""
    if not isinstance(readings, list) or not readings:
        return "readings must be a non-empty list of numbers"
    for index, value in enumerate(readings):
        if type(value) not in (int, float) or not math.isfinite(value):
            return "readings[%d] is not a finite number" % index
    return None
