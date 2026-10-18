"""Nightly shelf snapshot writer."""

HEADER = "SHELF/2"


def _row(sku, count):
    return sku + ";" + str(count)


def snapshot_text(counts):
    lines = [HEADER]
    for sku in sorted(counts):
        lines.append(_row(sku, counts[sku]))
    return "\n".join(lines) + "\n"


def write_snapshot(path, counts):
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(snapshot_text(counts))
