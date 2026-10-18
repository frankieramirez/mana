"""Product verification for invoice totals."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from invoice.totals import invoice_total_cents  # noqa: E402

CASES = [
    ("no discount", [(2, 450), (1, 99)], 0, 999),
    ("whole-cent discount", [(4, 250)], 10, 900),
    ("half-cent discount rounds up", [(3, 333)], 15, 849),
    ("empty invoice", [], 25, 0),
]

failed = 0
for name, lines, percent, expected in CASES:
    actual = invoice_total_cents(lines, percent)
    if actual == expected:
        print(f"ok   {name}: {actual}")
    else:
        failed += 1
        print(f"FAIL {name}: got {actual}, expected {expected}")
if failed:
    print(f"check_totals: {failed} of {len(CASES)} cases failed")
    sys.exit(1)
print(f"check_totals: all {len(CASES)} cases passed")
