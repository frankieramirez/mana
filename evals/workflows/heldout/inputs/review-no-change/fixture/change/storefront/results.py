from catalog.search import search


def results_page(products, query):
    """Rows for the search results page, in the order search returns them."""
    return [{"name": p["name"], "score": p["score"]} for p in search(products, query, limit=10)]
