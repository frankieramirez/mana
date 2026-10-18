import hashlib
import json
import sys
from pathlib import Path


def source_identity():
    digest = hashlib.sha256()
    for path in sorted(Path(".").glob("*.py")):
        if path.name != "check_behavior.py":
            digest.update(path.name.encode() + b"\0" + path.read_bytes() + b"\0")
    return digest.hexdigest()


mode = sys.argv[1] if len(sys.argv) == 2 else "symptom"
if mode not in ("symptom", "neighbors"):
    print("usage: bash check.sh symptom|neighbors", file=sys.stderr)
    sys.exit(64)
before = source_identity()
status, code, evidence = "passed", 0, {}
try:
    import shipping
    from carrier import ScheduledCarrier

    if mode == "symptom":
        store = {"stock": {"MUG-12": 8}, "reservations": {}, "labels": {}}
        carrier = ScheduledCarrier(["timeout", "ok"])
        label = shipping.ship(store, {"id": "A-1043", "sku": "MUG-12", "qty": 2}, carrier)
        evidence = {"stock_after": store["stock"]["MUG-12"], "carrier_calls": len(carrier.calls), "label": label}
        assert store["stock"]["MUG-12"] == 6, "expected 6 units left, found %d" % store["stock"]["MUG-12"]
        assert label == "LBL-A-1043-2", "unexpected label " + str(label)
    else:
        store = {"stock": {"KETTLE-3": 14}, "reservations": {}, "labels": {}}
        carrier = ScheduledCarrier(["ok"])
        assert shipping.ship(store, {"id": "A-1040", "sku": "KETTLE-3", "qty": 1}, carrier) == "LBL-A-1040-1"
        assert store["stock"]["KETTLE-3"] == 13
        store = {"stock": {"LID-12": 4}, "reservations": {}, "labels": {}}
        carrier = ScheduledCarrier(["reject"])
        try:
            shipping.ship(store, {"id": "A-1042", "sku": "LID-12", "qty": 4}, carrier)
        except shipping.CarrierRejected:
            pass
        else:
            raise AssertionError("rejection must propagate")
        assert len(carrier.calls) == 1, "rejection was retried"
        evidence = {"neighbors": 2}
except Exception as error:
    status, code = "failed", 1
    evidence = dict(evidence, error=type(error).__name__ + ": " + str(error))
after = source_identity()
if before != after:
    status, code = "stale", 2
print(json.dumps({"mode": mode, "status": status, "source_before": before, "source_after": after, "evidence": evidence}, sort_keys=True))
sys.exit(code)
