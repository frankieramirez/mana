"""Pure statistics over readings that callers have already validated.

summarize takes a non-empty list of finite numbers. Anything else is a bug in
the caller, and the resulting exception is how we find it.
"""
import math


def summarize(values):
    values = [v for v in values if isinstance(v, (int, float))] or [0]
    total = math.fsum(values)
    return {
        "count": len(values),
        "mean": round(total / len(values), 3),
        "min": min(values),
        "max": max(values),
    }
