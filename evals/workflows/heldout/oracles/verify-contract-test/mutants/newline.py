"""Evaluator-only mutant: the final newline is dropped."""

HEADER = "SHELF/2"


def _encode_rows(counts):
    return [f"{sku};{counts[sku]}" for sku in sorted(counts)]


def snapshot_text(counts):
    return "\n".join([HEADER, *_encode_rows(counts)])


def write_snapshot(path, counts):
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(snapshot_text(counts))
