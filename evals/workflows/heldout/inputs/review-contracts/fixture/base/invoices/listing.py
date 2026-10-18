from invoices.access import can_view


def list_invoices(store, viewer, org_id, limit=50):
    rows = [inv for inv in store.for_org(org_id) if can_view(viewer, inv)]
    rows.sort(key=lambda inv: inv.issued_on, reverse=True)
    return rows[:limit]
