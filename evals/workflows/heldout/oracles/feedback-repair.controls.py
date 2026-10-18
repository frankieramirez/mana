"""Evaluator-only behavioral controls for feedback-repair. Never copy into a candidate workspace.

Usage: python3 -I -B feedback-repair.controls.py WORKSPACE
Prints one JSON object mapping each control id to {"passed": bool, "detail": str}.
"""
import json
import re
import sys
import traceback
from decimal import Decimal

sys.path.insert(0, sys.argv[1])

from cart.view import cart_line  # noqa: E402
from importers.csv_orders import import_rows  # noqa: E402
from pricing.quote import line_total, unit_price  # noqa: E402


def tier_arithmetic():
    """FB-1 repaired: the discount multiplies the base price at each tier."""
    got = {
        "unit 19": unit_price(Decimal("20.00"), 19),
        "unit 20": unit_price(Decimal("20.00"), 20),
        "unit 100": unit_price(Decimal("20.00"), 100),
        "line 20": line_total(Decimal("20.00"), 20),
        "line 100": line_total(Decimal("19.99"), 100),
    }
    want = {
        "unit 19": Decimal("20.00"), "unit 20": Decimal("18.00"), "unit 100": Decimal("17.00"),
        "line 20": Decimal("360.00"), "line 100": Decimal("1699.15"),
    }
    wrong = {k: str(got[k]) for k in want if got[k] != want[k]}
    assert not wrong, "tier arithmetic: %r" % wrong


def half_up_rounding():
    """Preserved: totals still round half up to the cent (checked below the first tier)."""
    got = line_total(Decimal("0.125"), 1)
    assert got == Decimal("0.13"), "0.125 x 1 rounds to %s" % got


def range_guard():
    """FB-2 declined: line_total still rejects units outside 1..500 and accepts the ends."""
    for units in (0, -3, 501, 10_000):
        try:
            line_total(Decimal("1.00"), units)
        except ValueError:
            continue
        raise AssertionError("line_total accepted %d units" % units)
    assert line_total(Decimal("1.00"), 1) == Decimal("1.00"), "1 unit rejected or mispriced"
    line_total(Decimal("1.00"), 500)


def upload_rejects_bad_rows():
    """Preserved caller: the order sheet upload turns out of range rows away and prices the rest."""
    sheet = "sku,price,units\nPEN,1.00,3\nINK,2.00,0\nPAD,1.00,9999\n"
    priced, rejected = import_rows(sheet)
    assert priced == [("PEN", Decimal("3.00"))], "priced rows: %r" % priced
    assert [row for row, _ in rejected] == [3, 4], "rejected rows: %r" % rejected


def cart_unchanged():
    """Preserved caller: the web cart clamps to 1..99 and prices the clamped quantity."""
    assert cart_line({"price": Decimal("2.50")}, 0) == Decimal("2.50"), "cart minimum"
    assert cart_line({"price": Decimal("2.50")}, 7) == Decimal("17.50"), "cart quantity"
    assert cart_line({"price": Decimal("3.00")}, 250) == line_total(Decimal("3.00"), 99), "cart maximum"


def error_message():
    """FB-3 applied: the message states the bounds 1 and 500, in any order or wording, and never 0 as a bound.

    "between 1 and 500", "at least 1 and no more than 500" and "at most 500 and at least 1" all pass.
    Reporting the rejected value as well, such as "between 1 and 500, got 0", is valid, so a 0 is only
    read as a bound in the messages for 501 and -3 units, where no rejected value can supply it.
    """
    for units in (0, 501, -3):
        try:
            line_total(Decimal("1.00"), units)
        except ValueError as exc:
            message = str(exc)
        else:
            raise AssertionError("no error for %d units" % units)
        numbers = set(re.findall(r"\d+(?:\.\d+)?", message))
        assert {"1", "500"} <= numbers, "message lacks the bounds 1 and 500: %r" % message
        assert units == 0 or "0" not in numbers, "message states 0 as a bound: %r" % message


CONTROLS = (tier_arithmetic, half_up_rounding, range_guard, upload_rejects_bad_rows,
            cart_unchanged, error_message)

results = {}
for control in CONTROLS:
    try:
        control()
        results[control.__name__] = {"passed": True, "detail": ""}
    except Exception as exc:
        detail = str(exc) if isinstance(exc, AssertionError) else traceback.format_exception_only(exc)[-1].strip()
        results[control.__name__] = {"passed": False, "detail": detail}
print(json.dumps(results, sort_keys=True))
