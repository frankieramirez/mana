# Review batch 7: pricing/quote.py

FB-1, line 17. `unit_price` subtracts the rate from the price. A 20.00 item bought 20 at a time comes out at 19.90 each instead of 18.00. It should multiply: `base * (1 - discount_rate(units))`.

FB-2, line 21. This range check is redundant. The cart already clamps quantity to 1..99, so `line_total` never sees a bad value. Drop the check to simplify.

FB-3, line 22. The error says "between 0 and 500", but 0 is rejected. Say "between 1 and 500".
