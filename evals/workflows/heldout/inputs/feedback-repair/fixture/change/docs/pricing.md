# Pricing rules

- Volume discount: 10% off each unit from 20 units, 15% off each unit from 100 units.
- A line holds 1 to 500 units. `line_total` raises `ValueError` for anything else.
- Line totals round half up to the cent.
- Two callers price lines: the web cart (`cart/view.py`) and the order sheet upload (`importers/csv_orders.py`). The upload passes the units from each sheet row as written and relies on `line_total` to turn bad rows away.
