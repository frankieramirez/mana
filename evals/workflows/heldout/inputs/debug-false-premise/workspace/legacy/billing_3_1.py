"""Release 3.1 invoice arithmetic, kept unchanged for audit replays.

Amounts were integers in ten-thousandths of a currency unit. Display and
totals rounded half up to the cent.
"""


def _units(text):
    return round(float(text) * 10000)


def _cents(units):
    sign = -1 if units < 0 else 1
    cents = (abs(units) + 50) // 100
    return "%s%d.%02d" % ("-" if sign < 0 and cents else "", cents // 100, cents % 100)


def invoice(lines):
    amounts = [_units(line["unit_price"]) * int(line["quantity"]) for line in lines]
    return {"lines": [_cents(a) for a in amounts], "total": _cents(sum(amounts))}
