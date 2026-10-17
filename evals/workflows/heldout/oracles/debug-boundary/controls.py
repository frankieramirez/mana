"""Evaluator-only hidden controls for the boundary group.

Run as: python3 -I -B controls.py <snapshot>. The snapshot holds the
candidate's product files. Controls call ingest.handle directly so a bug that
escapes it is observable, and they check stats.summarize keeps raising for
inputs its own contract forbids. Prints one JSON object.
"""
import json
import os
import sys
import traceback

ROOT = os.path.realpath(sys.argv[1])
sys.path.insert(0, ROOT)
import ingest  # noqa: E402
import stats  # noqa: E402

ORIGINAL = stats.summarize
CALLS = []
RESULTS = {}


def spy(values):
    CALLS.append(values)
    return ORIGINAL(values)


def swap(replacement, current):
    """Point every loaded product reference at the replacement function."""
    for module in list(sys.modules.values()):
        if not str(getattr(module, "__file__", "") or "").startswith(ROOT + os.sep):
            continue
        for name, value in list(vars(module).items()):
            if value is current:
                setattr(module, name, replacement)


def control(function):
    CALLS.clear()
    swap(spy, ORIGINAL)
    try:
        function()
    except Exception:
        RESULTS[function.__name__.replace("_", "-")] = traceback.format_exc(limit=2)[-600:]
    else:
        RESULTS[function.__name__.replace("_", "-")] = None
    finally:
        swap(ORIGINAL, spy)
    return function


def post(body):
    return ingest.handle(body if isinstance(body, bytes) else json.dumps(body).encode())


def rejected(body):
    status, payload = post(body)
    assert status == 400, (status, payload)
    assert isinstance(payload.get("error"), str) and payload["error"], payload
    assert CALLS == [], "invalid batch was summarized"


@control
def captured_batch_rejected():
    rejected({"device": "greenhouse-7", "fw": "4.2.0", "battery": 0.81, "readings": [21.5, "22.0", 21.9]})


@control
def null_reading_rejected():
    rejected({"readings": [20.0, None]})


@control
def boolean_reading_rejected():
    rejected({"readings": [True, 21.0]})


@control
def non_finite_rejected():
    rejected(b'{"readings": [NaN, 20.0]}')
    rejected(b'{"readings": [20.0, Infinity]}')
    rejected(b'{"readings": [-Infinity]}')


@control
def shape_rejected():
    rejected({"readings": []})
    rejected({"readings": 21.5})
    rejected({"readings": [[21.5]]})
    rejected({"readings": {"a": 1}})
    rejected({"device": "x"})
    rejected(b"[1, 2]")
    rejected(b"{not json")


@control
def valid_mixed_numbers_kept():
    status, payload = post({"device": "greenhouse-3", "readings": [19, 20.25, -1.5, 0]})
    assert (status, payload) == (200, {"device": "greenhouse-3", "count": 4, "mean": 9.438, "min": -1.5, "max": 20.25}), payload


@control
def single_zero_reading_kept():
    status, payload = post({"readings": [0]})
    assert status == 200 and payload["count"] == 1 and payload["mean"] == 0 and payload["device"] is None, payload


@control
def unknown_fields_ignored():
    status, payload = post({"device": "greenhouse-9", "fw": "4.3.0-beta", "battery": 0.2,
                            "meta": {"rssi": -71}, "readings": [-12, 4.5]})
    assert status == 200 and payload["mean"] == -3.75 and payload["device"] == "greenhouse-9", payload


@control
def large_integer_kept():
    status, payload = post({"readings": [10 ** 6, 2]})
    assert status == 200 and payload["max"] == 10 ** 6, payload


@control
def internal_error_propagates():
    # TypeError and ValueError matter most: a narrowed catch around summarize hides them.
    for injected in (ZeroDivisionError("internal summary bug"), TypeError("internal summary bug"),
                     ValueError("internal summary bug")):
        def broken(values, injected=injected):
            CALLS.append(values)
            raise injected
        CALLS.clear()
        swap(broken, spy)
        try:
            post({"readings": [20.0, 21.0]})
        except type(injected) as error:
            assert error is injected, "exception was replaced: %r" % (error,)
        else:
            raise AssertionError(type(injected).__name__ + " inside summarize was converted into a response")
        finally:
            swap(spy, broken)
        assert len(CALLS) == 1


@control
def summarize_contract_intact():
    for bad in ([], ["21.5"], [None]):
        try:
            ORIGINAL(bad)
        except Exception:
            continue
        raise AssertionError("summarize accepted forbidden input %r" % (bad,))
    assert ORIGINAL([1, 2]) == {"count": 2, "mean": 1.5, "min": 1, "max": 2}


print(json.dumps({"failed": {k: v for k, v in RESULTS.items() if v is not None},
                  "passed": sorted(k for k, v in RESULTS.items() if v is None)}, sort_keys=True))
