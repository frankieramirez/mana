"""Evaluator-only hidden controls for the partial-retry group.

Run as: python3 -I -B controls.py <snapshot>. The snapshot holds the
candidate's product files. The carrier double here is the evaluator's own, so
an edited carrier.py cannot change the result. Prints one JSON object.
"""
import json
import sys
import traceback

sys.path.insert(0, sys.argv[1])
import shipping  # noqa: E402

RESULTS = {}


class Carrier:
    def __init__(self, schedule, other=None):
        self.schedule = list(schedule)
        self.calls = []
        self.other = other

    def create_label(self, order_id):
        self.calls.append(order_id)
        if not self.schedule:
            raise RuntimeError("evaluator carrier: call beyond schedule")
        outcome = self.schedule.pop(0)
        if outcome == "timeout":
            raise shipping.TransientCarrierError(order_id)
        if outcome == "reject":
            raise shipping.CarrierRejected(order_id)
        if outcome == "bug":
            raise self.other
        return "LBL-" + order_id + "-" + str(len(self.calls))


def control(function):
    try:
        function()
    except Exception:
        RESULTS[function.__name__.replace("_", "-")] = traceback.format_exc(limit=2)[-600:]
    else:
        RESULTS[function.__name__.replace("_", "-")] = None
    return function


def fresh(stock=8):
    return {"stock": {"MUG-12": stock}, "reservations": {}, "labels": {}}


ORDER = {"id": "A-1043", "sku": "MUG-12", "qty": 2}


def raises(kind, call):
    try:
        call()
    except kind as error:
        return error
    raise AssertionError("expected " + kind.__name__)


@control
def retry_single_reservation():
    store, carrier = fresh(), Carrier(["timeout", "ok"])
    assert shipping.ship(store, dict(ORDER), carrier) == "LBL-A-1043-2"
    assert store == {"stock": {"MUG-12": 6}, "reservations": {"A-1043": 2}, "labels": {"A-1043": "LBL-A-1043-2"}}, store
    assert len(carrier.calls) == 2


@control
def retry_two_timeouts_then_label():
    store, carrier = fresh(), Carrier(["timeout", "timeout", "ok"])
    assert shipping.ship(store, dict(ORDER), carrier) == "LBL-A-1043-3"
    assert store["stock"]["MUG-12"] == 6 and len(carrier.calls) == 3


@control
def retry_exhausted_keeps_reservation():
    store, carrier = fresh(), Carrier(["timeout"] * 3)
    raises(shipping.TransientCarrierError, lambda: shipping.ship(store, dict(ORDER), carrier))
    assert len(carrier.calls) == 3, carrier.calls
    assert store == {"stock": {"MUG-12": 6}, "reservations": {"A-1043": 2}, "labels": {}}, store


@control
def attempts_parameter_honored():
    store, carrier = fresh(), Carrier(["timeout"] * 4 + ["ok"])
    assert shipping.ship(store, dict(ORDER), carrier, attempts=5) == "LBL-A-1043-5"
    assert store["stock"]["MUG-12"] == 6
    store, carrier = fresh(), Carrier(["timeout"])
    raises(shipping.TransientCarrierError, lambda: shipping.ship(store, dict(ORDER), carrier, attempts=1))
    assert len(carrier.calls) == 1 and store["stock"]["MUG-12"] == 6


@control
def rejection_is_final():
    store, carrier = fresh(stock=100), Carrier(["reject"])
    raises(shipping.CarrierRejected, lambda: shipping.ship(store, dict(ORDER), carrier))
    assert len(carrier.calls) == 1
    assert store == {"stock": {"MUG-12": 98}, "reservations": {"A-1043": 2}, "labels": {}}, store


@control
def out_of_stock_before_carrier():
    store, carrier = fresh(stock=1), Carrier([])
    raises(shipping.OutOfStock, lambda: shipping.ship(store, dict(ORDER), carrier))
    assert carrier.calls == [] and store == fresh(stock=1), store


@control
def redelivery_after_crash():
    store = {"stock": {"MUG-12": 8}, "reservations": {"A-1043": 2}, "labels": {}}
    carrier = Carrier(["ok"])
    assert shipping.ship(store, dict(ORDER), carrier) == "LBL-A-1043-1"
    assert store == {"stock": {"MUG-12": 8}, "reservations": {"A-1043": 2}, "labels": {"A-1043": "LBL-A-1043-1"}}, store


@control
def redelivery_after_crash_with_timeout():
    store = {"stock": {"MUG-12": 8}, "reservations": {"A-1043": 2}, "labels": {}}
    carrier = Carrier(["timeout", "ok"])
    assert shipping.ship(store, dict(ORDER), carrier) == "LBL-A-1043-2"
    assert store["stock"]["MUG-12"] == 8 and len(carrier.calls) == 2, store


@control
def redelivery_after_crash_last_stock():
    # The order's own reservation took the last units; re-delivery must still ship.
    store = {"stock": {"LID-12": 0}, "reservations": {"A-1042": 4}, "labels": {}}
    carrier = Carrier(["ok"])
    assert shipping.ship(store, {"id": "A-1042", "sku": "LID-12", "qty": 4}, carrier) == "LBL-A-1042-1"
    assert store == {"stock": {"LID-12": 0}, "reservations": {"A-1042": 4}, "labels": {"A-1042": "LBL-A-1042-1"}}, store


@control
def repeat_after_label():
    store, carrier = fresh(), Carrier(["ok"])
    first = shipping.ship(store, dict(ORDER), carrier)
    assert shipping.ship(store, dict(ORDER), carrier) == first
    assert len(carrier.calls) == 1 and store["stock"]["MUG-12"] == 6


@control
def independent_orders_same_sku():
    store, carrier = fresh(), Carrier(["timeout", "ok", "ok"])
    shipping.ship(store, dict(ORDER), carrier)
    shipping.ship(store, {"id": "A-1044", "sku": "MUG-12", "qty": 3}, carrier)
    assert store["stock"]["MUG-12"] == 3, store
    assert store["reservations"] == {"A-1043": 2, "A-1044": 3}


@control
def programming_error_propagates():
    # Builtin timeouts and connection errors, leaf classes included, are not carrier timeouts under the contract.
    for injected in (KeyError("label_format"), TimeoutError("socket read"), InterruptedError("signal"),
                     ConnectionError("connection lost"), ConnectionResetError("reset by peer"),
                     BrokenPipeError("broken pipe"), ConnectionRefusedError("refused"),
                     ConnectionAbortedError("aborted")):
        store, carrier = fresh(stock=100), Carrier(["bug", "ok"], other=injected)
        error = raises(type(injected), lambda: shipping.ship(store, dict(ORDER), carrier))
        assert error is injected, "exception was replaced: %r" % (error,)
        assert len(carrier.calls) == 1, type(injected).__name__ + " was retried"


@control
def malformed_order_propagates():
    store, carrier = fresh(), Carrier(["ok"])
    raises(KeyError, lambda: shipping.ship(store, {"id": "A-1045", "sku": "MUG-12"}, carrier))
    assert carrier.calls == [] and store["stock"]["MUG-12"] == 8


print(json.dumps({"failed": {k: v for k, v in RESULTS.items() if v is not None},
                  "passed": sorted(k for k, v in RESULTS.items() if v is None)}, sort_keys=True))
