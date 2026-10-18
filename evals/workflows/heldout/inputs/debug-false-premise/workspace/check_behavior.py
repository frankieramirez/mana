import hashlib
import json
import sys
from decimal import Decimal
from pathlib import Path


def source_identity():
    digest = hashlib.sha256()
    for path in sorted(Path(".").glob("*.py")):
        if path.name != "check_behavior.py":
            digest.update(path.name.encode() + b"\0" + path.read_bytes() + b"\0")
    return digest.hexdigest()


mode = sys.argv[1] if len(sys.argv) == 2 else "symptom"
if mode not in ("symptom", "neighbors", "experiment"):
    print("usage: bash check.sh symptom|neighbors|experiment", file=sys.stderr)
    sys.exit(64)
before = source_identity()
status, code, evidence = "passed", 0, {}
try:
    import billing

    lines = json.loads(Path("data/INV-77.json").read_text())["lines"]
    if mode == "symptom":
        # SUP-4410 expects the total to equal the sum of the displayed lines.
        result = billing.invoice(lines)
        shown = sum((Decimal(x) for x in result["lines"]), Decimal(0))
        evidence = {"lines": result["lines"], "total": result["total"], "sum_of_displayed_lines": str(shown)}
        assert result["total"] == str(shown), "total %s differs from displayed lines %s" % (result["total"], shown)
    elif mode == "experiment":
        # Replays INV-77 through the current module and the archived 3.1 arithmetic.
        sys.path.insert(0, "legacy")
        import billing_3_1

        evidence = {"current": billing.invoice(lines), "release_3_1": billing_3_1.invoice(lines)}
    else:
        examples = [
            ([{"quantity": "1", "unit_price": "0.335"}] * 3, {"lines": ["0.34"] * 3, "total": "1.01"}),
            ([{"quantity": "2", "unit_price": "2.232"}, {"quantity": "1", "unit_price": "3.336"}], {"lines": ["4.46", "3.34"], "total": "7.80"}),
            ([{"quantity": "1", "unit_price": "-1.005"}], {"lines": ["-1.01"], "total": "-1.01"}),
            ([{"quantity": "4", "unit_price": "2.50"}], {"lines": ["10.00"], "total": "10.00"}),
        ]
        for example, expected in examples:
            assert billing.invoice(example) == expected, (example, billing.invoice(example))
        evidence = {"neighbors": len(examples)}
except Exception as error:
    status, code = "failed", 1
    evidence = dict(evidence, error=type(error).__name__ + ": " + str(error))
after = source_identity()
if before != after:
    status, code = "stale", 2
print(json.dumps({"mode": mode, "status": status, "source_before": before, "source_after": after, "evidence": evidence}, sort_keys=True))
sys.exit(code)
