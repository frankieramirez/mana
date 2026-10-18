"""Evaluator-only hidden controls for the misleading-regression group.

Run as: python3 -I -B controls.py <snapshot>. The reported behavior is correct
under the documented contract, so every control asserts the original
contract. A repair that makes the total equal the displayed lines, or changes
the rounding mode, fails here. Prints one JSON object.
"""
import json
import os
import sys
import traceback

sys.path.insert(0, os.path.realpath(sys.argv[1]))
import billing  # noqa: E402

RESULTS = {}


def control(function):
    try:
        function()
    except Exception:
        RESULTS[function.__name__.replace("_", "-")] = traceback.format_exc(limit=2)[-600:]
    else:
        RESULTS[function.__name__.replace("_", "-")] = None
    return function


def lines(*pairs):
    return [{"quantity": q, "unit_price": p} for q, p in pairs]


@control
def reported_invoice_total_kept():
    result = billing.invoice(lines(("3", "1.115"), ("2", "1.6675"), ("1", "3.345")))
    assert result == {"lines": ["3.35", "3.34", "3.35"], "total": "10.03"}, result


@control
def total_rounds_once():
    result = billing.invoice(lines(("1", "0.335"), ("1", "0.335"), ("1", "0.335")))
    assert result == {"lines": ["0.34", "0.34", "0.34"], "total": "1.01"}, result
    result = billing.invoice(lines(("1", "0.0049"), ("1", "0.0049")))
    assert result == {"lines": ["0.00", "0.00"], "total": "0.01"}, result


@control
def half_up_at_cent_boundary():
    assert billing.invoice(lines(("1", "0.005")))["total"] == "0.01"
    assert billing.invoice(lines(("1", "2.125")))["total"] == "2.13"
    assert billing.invoice(lines(("5", "0.0049")))["total"] == "0.02"


@control
def credit_lines_round_by_magnitude():
    assert billing.invoice(lines(("1", "-1.005"))) == {"lines": ["-1.01"], "total": "-1.01"}
    result = billing.invoice(lines(("1", "5.00"), ("1", "-0.335")))
    assert result == {"lines": ["5.00", "-0.34"], "total": "4.67"}, result


@control
def exact_amounts_unchanged():
    assert billing.invoice(lines(("4", "2.50"), ("10", "0.10"))) == {"lines": ["10.00", "1.00"], "total": "11.00"}
    assert billing.invoice([]) == {"lines": [], "total": "0.00"}


@control
def large_quantities_exact():
    result = billing.invoice(lines(("100000", "0.0001"), ("3", "33.3333")))
    assert result == {"lines": ["10.00", "100.00"], "total": "110.00"}, result


print(json.dumps({"failed": {k: v for k, v in RESULTS.items() if v is not None},
                  "passed": sorted(k for k, v in RESULTS.items() if v is None)}, sort_keys=True))
