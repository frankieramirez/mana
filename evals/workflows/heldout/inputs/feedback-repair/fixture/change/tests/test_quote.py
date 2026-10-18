import unittest
from decimal import Decimal

from pricing.quote import line_total


class LineTotal(unittest.TestCase):
    def test_small_order_has_no_discount(self):
        self.assertEqual(line_total(Decimal("4.20"), 3), Decimal("12.60"))

    def test_rejects_zero_units(self):
        with self.assertRaises(ValueError):
            line_total(Decimal("4.20"), 0)
