# 41: Hide archived invoices

Archived invoices clutter the dashboard.

Acceptance criteria:

- Members of an org see that org's invoices that are not archived.
- Admins of an org also see that org's archived invoices, only when they ask for them with `include_archived`.
- No one sees another org's invoices. The compliance export described in `docs/callers.md` keeps its current access.
- Listings stay newest first, and `limit` keeps the newest rows.

Out of scope: signed out behavior, which stays as it is.
