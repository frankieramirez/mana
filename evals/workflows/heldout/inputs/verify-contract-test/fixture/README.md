# Shelf stock export

`shelf/export.py` writes the nightly stock snapshot. The replenishment service is a separate deployment that reads the written file with `replenish/reader.py`; the two ship on different schedules, so the file format in `docs/snapshot-format.md` is the agreement between them.

Run the tests with:

    python3 -m unittest discover -s tests
