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
    import server

    log = []
    if mode == "symptom":
        result = server.dispatch(Path("samples/firmware-4.2.json").read_bytes(), log)
        evidence = {"status": result[0], "body": result[1], "logged_tracebacks": len(log)}
        assert result[0] == 400, "firmware 4.2 batch answered %d" % result[0]
        assert result[1].get("error"), "400 without an error message"
    else:
        result = server.dispatch(Path("samples/firmware-4.1.json").read_bytes(), log)
        assert result == (200, {"device": "greenhouse-3", "count": 4, "mean": 9.438, "min": -1.5, "max": 20.25}), result
        assert server.dispatch(b"{not json", log)[0] == 400
        assert server.dispatch(b'{"device": "greenhouse-3"}', log)[0] == 400
        assert log == [], log
        evidence = {"neighbors": 3}
except Exception as error:
    status, code = "failed", 1
    evidence = dict(evidence, error=type(error).__name__ + ": " + str(error))
after = source_identity()
if before != after:
    status, code = "stale", 2
print(json.dumps({"mode": mode, "status": status, "source_before": before, "source_after": after, "evidence": evidence}, sort_keys=True))
sys.exit(code)
