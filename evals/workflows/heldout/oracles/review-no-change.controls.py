"""Evaluator-only behavioral controls for review-no-change. Never copy into a candidate workspace.

Usage: python3 -I -B review-no-change.controls.py WORKSPACE BASE_SEARCH_PY
BASE_SEARCH_PY is the frozen pre-change catalog/search.py from the evaluator's copy of the inputs.
Prints one JSON object mapping each control id to {"passed": bool, "detail": str}.
"""
import importlib.util
import json
import random
import sys
import traceback

sys.path.insert(0, sys.argv[1])

from catalog import search as candidate  # noqa: E402

spec = importlib.util.spec_from_file_location("frozen_base_search", sys.argv[2])
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)

WORDS = ["trail", "Shoe", "RAIN", "jacket", "run", "outdoor", "o", "ΟΔΟΣ", "οδος", "Straße", "strasse",
         "İzmir", "izmir", "café", "CAFÉ", "a", "e", "sh", "ΣΑΣ", "σας"]
FIXED = [
    {"name": "Trail Shoe", "tags": ["running", "outdoor"], "score": 80},
    {"name": "Road Shoe", "tags": ["running"], "score": 80},
    {"name": "Road Shoe", "tags": [], "score": 80},
    {"name": "Rain Jacket", "tags": ["outdoor"], "score": 95},
    {"name": "ΟΔΟΣ", "tags": ["ΣΑΣ"], "score": 10},
    {"name": "Straße", "tags": ["café"], "score": 10},
    {"name": "İzmir Map", "tags": [], "score": 0},
    {"name": "", "tags": ["only tags"], "score": 100},
]


def corpus(rng, size):
    items = []
    for _ in range(size):
        name = " ".join(rng.choice(WORDS) for _ in range(rng.randint(0, 3)))
        tags = [rng.choice(WORDS) for _ in range(rng.randint(0, 3))]
        items.append({"name": name, "tags": tags, "score": rng.choice([0, 10, 50, 80, 80, 95, 100])})
    return items


def queries(rng):
    out = ["", "   ", "o", "shoe", "SHOE run", "οδος", "ΣΑΣ", "straße", "i̇zmir", "café"]
    out += [" ".join(rng.choice(WORDS) for _ in range(rng.randint(1, 3))) for _ in range(40)]
    return out


def same_results():
    """The refactor returns the same objects in the same order for every allowed input tried."""
    rng = random.Random(20261017)
    checked = 0
    for size in (0, 1, 2, 5, 12, 30):
        for _ in range(8):
            products = FIXED + corpus(rng, size)
            rng.shuffle(products)
            for query in queries(rng):
                for limit in (20, 3, 1, 0):
                    want = base.search(products, query, limit)
                    got = candidate.search(products, query, limit)
                    if [id(p) for p in got] != [id(p) for p in want]:
                        raise AssertionError("differs for query %r limit %d: %r vs %r" % (
                            query, limit, [p["name"] for p in got], [p["name"] for p in want]))
                    checked += 1
    assert checked > 1000, "too few comparisons: %d" % checked


def matches_agrees():
    """The new public helper applies the same rule search uses."""
    rng = random.Random(58)
    for product in FIXED + corpus(rng, 50):
        for query in queries(rng):
            words = query.lower().split()
            if not words:
                continue
            assert candidate.matches(product, words) == bool(base.search([product], query)), (
                "matches disagrees for %r with %r" % (product, words))


CONTROLS = (same_results, matches_agrees)

results = {}
for control in CONTROLS:
    try:
        control()
        results[control.__name__] = {"passed": True, "detail": ""}
    except Exception as exc:
        detail = str(exc) if isinstance(exc, AssertionError) else traceback.format_exception_only(exc)[-1].strip()
        results[control.__name__] = {"passed": False, "detail": detail}
print(json.dumps(results, sort_keys=True))
