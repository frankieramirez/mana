"""Replenishment service side: parses the nightly shelf snapshot file."""


def read_snapshot(text):
    lines = text.split("\n")
    if lines[0] != "SHELF/2" or lines[-1] != "":
        raise ValueError("unsupported snapshot")
    counts = {}
    for line in lines[1:-1]:
        sku, count = line.split(";")
        counts[sku] = int(count)
    return counts
