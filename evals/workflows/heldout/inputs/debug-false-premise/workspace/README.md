# Billing

`billing.py` computes invoice line amounts and totals. `docs/billing-contract.md` is the rounding contract. `legacy/billing_3_1.py` is the release 3.1 arithmetic, kept for audit replays.

Checks:

- `bash check.sh symptom` checks the expectation in `support/SUP-4410.md` against INV-77.
- `bash check.sh neighbors` runs the contract examples.
- `bash check.sh experiment` replays INV-77 through the current module and the 3.1 arithmetic and prints both results.

Each check prints one JSON line with its status and the source identity before and after the run.
