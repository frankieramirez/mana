def _haystack(product):
    return " ".join([product["name"], *product["tags"]]).lower()


def matches(product, words):
    """True when every lowercased query word occurs in the product's name or tags."""
    haystack = _haystack(product)
    return all(word in haystack for word in words)


def search(products, query, limit=20):
    """Products whose name or tags contain every word of the query.

    Best score first; equal scores keep alphabetical order by name.
    """
    words = query.lower().split()
    if not words:
        return []
    found = (product for product in products if matches(product, words))
    return sorted(found, key=lambda p: (-p["score"], p["name"]))[:limit]
