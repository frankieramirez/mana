from invoices.listing import list_invoices


def dashboard(store, session, org_id, show_archived=False):
    viewer = session.get("user")
    rows = list_invoices(store, viewer, org_id, include_archived=show_archived)
    return [inv.number for inv in rows]
