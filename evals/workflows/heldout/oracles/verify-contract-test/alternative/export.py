"""Evaluator-only: same observable snapshot bytes, different internals."""

HEADER = "SHELF/2"


def _lines(counts):
    yield HEADER
    for sku, count in sorted(counts.items()):
        yield "%s;%d" % (sku, count)


def snapshot_text(counts):
    return "".join(line + "\n" for line in _lines(counts))


def write_snapshot(path, counts):
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(snapshot_text(counts))
