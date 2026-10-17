"""Invoice amounts. Release 3.2 moved this module from integer arithmetic to Decimal."""
from decimal import ROUND_HALF_EVEN, Decimal

CENT = Decimal("0.01")


def line_amount(line):
    return Decimal(line["unit_price"]) * Decimal(line["quantity"])


def to_cents(amount):
    return amount.quantize(CENT, rounding=ROUND_HALF_EVEN)


def invoice(lines):
    amounts = [line_amount(line) for line in lines]
    return {
        "lines": [str(to_cents(amount)) for amount in amounts],
        "total": str(to_cents(sum(amounts, Decimal(0)))),
    }
