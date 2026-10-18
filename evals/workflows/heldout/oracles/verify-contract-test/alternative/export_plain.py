"""Evaluator-only: same snapshot bytes with independent internals.

No sorted(), open(), list(), HEADER name or fixture helper name, and
write_snapshot builds its own bytes instead of calling snapshot_text.
"""
import pathlib

_FORMAT_LINE = "SHELF/2"


def snapshot_text(counts):
    skus = [sku for sku in counts]
    skus.sort()
    text = _FORMAT_LINE + "\n"
    for sku in skus:
        text += "{};{}\n".format(sku, counts[sku])
    return text


def write_snapshot(path, counts):
    remaining = dict(counts)
    data = bytearray(b"SHELF/2\n")
    while remaining:
        sku = min(remaining)
        data += ("%s;%d\n" % (sku, remaining.pop(sku))).encode("utf-8")
    pathlib.Path(path).write_bytes(bytes(data))
