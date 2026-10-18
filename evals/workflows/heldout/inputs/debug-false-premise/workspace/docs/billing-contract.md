# Billing contract

Finance decision FIN-12 (2023) sets how invoice amounts round.

1. Each line amount is `unit_price × quantity`, computed exactly.
2. The invoice shows each line amount rounded half up to the cent.
3. The invoice total is the exact sum of the unrounded line amounts, rounded half up to the cent once.

Because rounding happens once for the total, the displayed lines can add up to a few cents more or less than the total. The total is the amount we charge. Example: three lines of `0.335` each display as `0.34`, `0.34` and `0.34`, which add up to `1.02`, while the total is `1.01` (exact sum `1.005`).

Quantities are whole numbers. Unit prices carry at most four decimals. Credit lines use negative unit prices and round half up by magnitude.
