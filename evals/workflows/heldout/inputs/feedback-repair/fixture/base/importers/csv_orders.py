import csv
from decimal import Decimal

from pricing.quote import line_total


def import_rows(text):
    """Price the rows of an uploaded order sheet. Bad rows are reported, not priced."""
    priced, rejected = [], []
    for number, row in enumerate(csv.DictReader(text.splitlines()), start=2):
        try:
            priced.append((row["sku"], line_total(Decimal(row["price"]), int(row["units"]))))
        except (ValueError, ArithmeticError) as exc:
            rejected.append((number, str(exc)))
    return priced, rejected
