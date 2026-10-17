"""Evaluator-only: same snapshot bytes without sorted(), open() or any fixture helper name."""
import pathlib

HEADER = "SHELF/2"


def snapshot_text(counts):
    skus = list(counts)
    skus.sort()
    text = HEADER + "\n"
    for sku in skus:
        text += "{};{}\n".format(sku, counts[sku])
    return text


def write_snapshot(path, counts):
    pathlib.Path(path).write_text(snapshot_text(counts), encoding="utf-8")
