# 58: Share the search matching rule

The autocomplete work planned for next sprint needs the same matching rule as search. Pull the rule out of `search` into a public `matches(product, words)` function that takes already lowercased query words.

Acceptance criteria:

- `search` returns exactly what it returned before for every input that `docs/catalog.md` allows, in the same order.
- `matches` is covered by a test.

Out of scope: autocomplete itself, ranking changes.
