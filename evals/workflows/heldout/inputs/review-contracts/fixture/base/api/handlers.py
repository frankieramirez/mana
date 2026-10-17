from invoices.listing import list_invoices


def dashboard(store, session, org_id):
    viewer = session.get("user")
    return [inv.number for inv in list_invoices(store, viewer, org_id)]
