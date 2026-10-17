from decimal import Decimal, ROUND_HALF_UP

CENT = Decimal("0.01")


def line_total(base, units):
    if units < 1:
        raise ValueError("units must be positive")
    return (base * units).quantize(CENT, rounding=ROUND_HALF_UP)
