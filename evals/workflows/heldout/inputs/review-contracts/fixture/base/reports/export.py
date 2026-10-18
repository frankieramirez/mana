from invoices.listing import list_invoices
from invoices.models import Principal

EXPORTER = Principal(name="ledger-export", role="auditor", org_id=None)


def export_org(store, org_id):
    """Nightly compliance export of one org's invoices. Read only."""
    return [inv.number for inv in list_invoices(store, EXPORTER, org_id, limit=10_000)]
