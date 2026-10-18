class InvoiceStore:
    def __init__(self, invoices):
        self._invoices = list(invoices)

    def for_org(self, org_id):
        return [inv for inv in self._invoices if inv.org_id == org_id]
