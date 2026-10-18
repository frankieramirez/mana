# Proposed fix for the 4.2 firmware 500s

From the #ops channel, 2026-10-14:

> Greenhouse devices on firmware 4.2 get 500s and retry all night. Easiest fix: wrap the `stats.summarize` call in `ingest.handle` with `try/except Exception` and return `400 {"error": "bad readings"}`. Then nothing in stats can ever take the endpoint down again.

Not reviewed yet.
