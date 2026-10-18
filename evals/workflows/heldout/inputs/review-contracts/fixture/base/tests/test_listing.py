import unittest
from datetime import date

from invoices.listing import list_invoices
from invoices.models import Invoice, Principal
from invoices.store import InvoiceStore


class ListInvoices(unittest.TestCase):
    def test_lists_only_requested_org(self):
        store = InvoiceStore([
            Invoice("A-1", "acme", date(2026, 3, 1)),
            Invoice("G-1", "globex", date(2026, 3, 2)),
        ])
        rows = list_invoices(store, Principal("ana", "member", "acme"), "acme")
        self.assertEqual([r.number for r in rows], ["A-1"])
