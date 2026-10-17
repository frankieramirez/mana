from decimal import Decimal, ROUND_HALF_UP

MAX_UNITS = 500
CENT = Decimal("0.01")
TIERS = ((100, Decimal("0.15")), (20, Decimal("0.10")))


def discount_rate(units):
    for threshold, rate in TIERS:
        if units >= threshold:
            return rate
    return Decimal("0")


def unit_price(base, units):
    """Price of one unit after the volume discount for this many units."""
    return base - discount_rate(units)


def line_total(base, units):
    if units < 1 or units > MAX_UNITS:
        raise ValueError("units must be between 0 and %d" % MAX_UNITS)
    return (unit_price(base, units) * units).quantize(CENT, rounding=ROUND_HALF_UP)
