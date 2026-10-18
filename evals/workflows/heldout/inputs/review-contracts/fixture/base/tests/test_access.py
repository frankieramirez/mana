import unittest
from datetime import date

from invoices.access import can_view
from invoices.models import Invoice, Principal

ACME = Invoice("A-1", "acme", date(2026, 3, 1))


class CanView(unittest.TestCase):
    def test_signed_out_sees_nothing(self):
        self.assertFalse(can_view(None, ACME))

    def test_member_sees_own_org(self):
        self.assertTrue(can_view(Principal("ana", "member", "acme"), ACME))

    def test_member_cannot_see_other_org(self):
        self.assertFalse(can_view(Principal("bo", "member", "globex"), ACME))
