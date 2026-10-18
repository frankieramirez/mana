from invoices.access import can_view


def list_invoices(store, viewer, org_id, include_archived=False, limit=50):
    rows = [inv for inv in store.for_org(org_id) if can_view(viewer, inv, include_archived)]
    rows.sort(key=lambda inv: inv.issued_on)
    return rows[:limit]
