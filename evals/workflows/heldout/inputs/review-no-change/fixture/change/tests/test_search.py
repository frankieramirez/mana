import unittest

from catalog.search import matches, search

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


class Matches(unittest.TestCase):
    def test_matches_name_or_tags(self):
        self.assertTrue(matches(PRODUCTS[0], ["trail", "outdoor"]))
        self.assertFalse(matches(PRODUCTS[1], ["outdoor"]))
