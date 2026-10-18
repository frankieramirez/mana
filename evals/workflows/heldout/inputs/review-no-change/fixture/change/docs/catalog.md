# Catalog search

Each product is a dict with `name` (str), `tags` (list of str) and `score` (int from 0 to 100).

`search(products, query, limit=20)` returns the products whose name or tags contain every whitespace separated word of the query, ignoring case. Results are ordered by score, highest first, and products with equal scores are ordered by name. A blank query returns no results. The storefront results page shows them in exactly this order.
