# Callers of the invoice access layer

- `api/handlers.py` serves the dashboard. It passes the signed in user as `viewer`, or `None` for a signed out visitor, who must see nothing.
- `reports/export.py` runs the nightly compliance export as the `ledger-export` service principal. That principal has role `auditor` and no org. Compliance requires it to read every invoice of any org, archived ones included. It never writes. It is configured in the deployment, so it does not appear in the users table.
