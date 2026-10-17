def search(products, query, limit=20):
    """Products whose name or tags contain every word of the query.

    Best score first; equal scores keep alphabetical order by name.
    """
    words = query.lower().split()
    if not words:
        return []
    results = []
    for product in products:
        haystack = product["name"].lower() + " " + " ".join(product["tags"]).lower()
        if all(word in haystack for word in words):
            results.append(product)
    results.sort(key=lambda p: p["name"])
    results.sort(key=lambda p: p["score"], reverse=True)
    return results[:limit]
