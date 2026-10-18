"""Evaluator-only mutant: rows keep insertion order instead of sku order."""

HEADER = "SHELF/2"


def _encode_rows(counts):
    return [f"{sku};{counts[sku]}" for sku in counts]


def snapshot_text(counts):
    return "\n".join([HEADER, *_encode_rows(counts)]) + "\n"


def write_snapshot(path, counts):
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(snapshot_text(counts))
