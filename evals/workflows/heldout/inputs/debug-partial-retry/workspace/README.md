# Shipping worker

`shipping.py` reserves stock and buys carrier labels. `docs/shipping.md` is the contract. `carrier.py` is a deterministic carrier double for local checks.

Checks:

- `bash check.sh symptom` replays the failing example from `incident.md`.
- `bash check.sh neighbors` runs the cases that already pass.

Each check prints one JSON line with its status and the source identity before and after the run.
