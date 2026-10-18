import unittest

from catalog.search import search

PRODUCTS = [
    {"name": "Trail Shoe", "tags": ["running", "outdoor"], "score": 80},
    {"name": "Road Shoe", "tags": ["running"], "score": 80},
    {"name": "Rain Jacket", "tags": ["outdoor"], "score": 95},
]


class Search(unittest.TestCase):
    def test_every_word_must_match(self):
        self.assertEqual([p["name"] for p in search(PRODUCTS, "running outdoor")], ["Trail Shoe"])

    def test_orders_by_score_then_name(self):
        names = [p["name"] for p in search(PRODUCTS, "o")]
        self.assertEqual(names, ["Rain Jacket", "Road Shoe", "Trail Shoe"])

    def test_blank_query(self):
        self.assertEqual(search(PRODUCTS, "   "), [])
