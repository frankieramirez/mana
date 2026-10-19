#!/usr/bin/env bash
# candidates.sh: find the project-control features a vague report could be about, without running anything.
#
#   candidates.sh --repo REPO (--query TEXT | --query-file FILE) [--scope static|local] [--limit N]
#
# Reads files only. Follows the Control: pointer with the bundled conform.sh (evidence for the
# pointer state, static for the map's gaps), then matches the report's words against each feature
# record's aliases, summary, reach routes, commands and steps, and its scenarios' steps. Each
# reach route or command is looked up in the feature's sourceRoots, so a route the source no
# longer mentions shows up as a discrepancy. Every candidate is inferred from record text and
# claims no behavior.
#
# --scope says whether control commands may run (default static). Under static the plan is empty.
# Under local, with a present control, the plan names the discovery commands (list --search,
# describe feature) and at most one feature run: the top candidate, when it has a bound scenario
# and no other candidate ties it. This script runs none of them.
#
# Prints one JSON document. Exit 0 when at least one candidate matched, 3 when none did or no
# feature records exist, 2 on a usage error, 4 when python3 is missing. Python 3 standard library
# inside bash; no jq, no node, no pip package.

set -euo pipefail

usage() {
  awk 'NR == 1 { next } /^#/ { sub(/^# ?/, ""); print; next } { exit }' "${BASH_SOURCE[0]}"
}

case "${1:-}" in
  -h|--help) usage; exit 0 ;;
  "") usage >&2; exit 2 ;;
esac

command -v python3 >/dev/null 2>&1 || { echo "candidates.sh: python3 not found" >&2; exit 4; }

conform="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/conform.sh"
[ -f "$conform" ] || { echo "candidates.sh: conform.sh must sit beside this script" >&2; exit 2; }

python3 - "$conform" "$@" <<'PY'
import json, os, re, shlex, subprocess, sys

STOP = set("""the and for with this that was were been are you your our its his her they them their then than
there here when what which who why how not but have has had does did doing done can cant could would should
into onto from about after before again just only also very some any all each every more most other same such
off out over under now still yet get got see seen show shows showing page app""".split())
PHRASE_WEIGHT = 3


def usage_error(message):
    print(f"candidates.sh: {message}", file=sys.stderr)
    raise SystemExit(2)


def tokens(text):
    return re.findall(r"[a-z0-9]+", str(text).lower())


def words(text):
    return {w for w in tokens(text) if len(w) >= 3 and w not in STOP}


def has_phrase(phrase, query_tokens):
    want = tokens(phrase)
    if not want:
        return False
    return f" {' '.join(want)} " in f" {' '.join(query_tokens)} "


def read_json(path):
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def inside(root, rel):
    full = os.path.realpath(os.path.join(root, rel))
    return full if full == root or full.startswith(root + os.sep) else None


def conform(script, *args):
    proc = subprocess.run(["bash", script, *args], capture_output=True, text=True, timeout=120)
    try:
        return json.loads(proc.stdout)
    except ValueError:
        usage_error(f"conform.sh {args[0]} printed no JSON: {proc.stderr.strip()[:300]}")


def step_text(step):
    if isinstance(step, dict):
        return " ".join(str(v) for v in step.values() if isinstance(v, str))
    return step if isinstance(step, str) else ""


def mentioned_in(root, roots, needle):
    """Files under the feature's sourceRoots whose text contains the route or command."""
    hits = []
    for rel in roots if isinstance(roots, list) else []:
        base = inside(root, rel) if isinstance(rel, str) else None
        if not base or not os.path.exists(base):
            continue
        paths = [base] if os.path.isfile(base) else (
            os.path.join(d, n) for d, dirs, names in os.walk(base)
            for n in names if not any(p in (".git", "node_modules") for p in d.split(os.sep)))
        for path in paths:
            try:
                if os.path.getsize(path) > 2_000_000:
                    continue
                with open(path, encoding="utf-8") as fh:
                    if needle in fh.read():
                        hits.append(os.path.relpath(path, root))
            except (OSError, UnicodeDecodeError):
                continue
    return sorted(hits)


def main(argv):
    script, argv = argv[0], argv[1:]
    repo, query, scope, limit = None, None, "static", 5
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg in ("--repo", "--query", "--query-file", "--scope", "--limit") and i + 1 < len(argv):
            value = argv[i + 1]
            if arg == "--repo":
                repo = value
            elif arg == "--query":
                query = value
            elif arg == "--query-file":
                try:
                    with open(value, encoding="utf-8") as fh:
                        query = fh.read()
                except OSError as exc:
                    usage_error(f"cannot read --query-file: {exc}")
            elif arg == "--scope":
                scope = value
            else:
                limit = int(value) if value.isdigit() and int(value) > 0 else usage_error("--limit takes a positive integer")
            i += 2
            continue
        usage_error(f"unexpected argument {arg}")
    if repo is None or not os.path.isdir(repo):
        usage_error("--repo must name a directory")
    if scope not in ("static", "local"):
        usage_error("--scope is static or local")
    if not query or not words(query) and not re.search(r"/\S", query):
        usage_error("the query has no searchable words")
    root = os.path.realpath(repo)

    pointer = conform(script, "evidence", "--repo", root, "--scope", scope)
    static = conform(script, "static", root)
    control = pointer["control"]
    keys = static["control"]["keys"]
    gaps = [f for f in static["findings"] if f["severity"] == "error" and not f["rule"].startswith("control.")]
    no_records = any(f["rule"] == "feature.none" for f in gaps) or not static["counts"]["features"]
    map_state = "absent" if no_records else "incomplete" if gaps else "complete"

    query_tokens, query_words, lowered = tokens(query), words(query), query.lower()
    features_dir, scenarios_dir = keys["Features"].rstrip("/"), keys["Scenarios"].rstrip("/")
    candidates = []
    for fid in static["features"]:
        record = read_json(os.path.join(root, features_dir, f"{fid}.json")) or {}
        matched, hit_words, phrases = [], set(), 0
        for n, alias in enumerate(record.get("aliases") or []):
            if isinstance(alias, str) and has_phrase(alias, query_tokens):
                matched.append({"field": f"aliases[{n}]", "value": alias, "via": "phrase"})
                phrases += 1
        reach = []
        for n, entry in enumerate(record.get("reach") or []):
            if not isinstance(entry, dict):
                continue
            for key in ("route", "command", "shortcut"):
                value = entry.get(key)
                if not isinstance(value, str) or not value:
                    continue
                if len(value) > 1 and value.lower() in lowered:
                    matched.append({"field": f"reach[{n}].{key}", "value": value, "via": "literal"})
                    phrases += 1
                found = mentioned_in(root, record.get("sourceRoots"), value)
                reach.append({key: value, "steps": [step_text(s) for s in entry.get("steps") or []], "inSources": found,
                              "discrepancy": None if found else f"{key} {value} appears in no file under sourceRoots"})
            got = query_words & words(" ".join(step_text(s) for s in entry.get("steps") or []))
            if got:
                matched.append({"field": f"reach[{n}].steps", "value": ", ".join(sorted(got)), "via": "words"})
                hit_words |= got
        for field in ("summary", "id"):
            got = query_words & words(record.get(field) or (fid if field == "id" else ""))
            if got:
                matched.append({"field": field, "value": ", ".join(sorted(got)), "via": "words"})
                hit_words |= got
        own_gaps = [g for g in gaps if g.get("path") and (
            g["path"] == f"{features_dir}/{fid}.json" or g["path"].startswith(f"{scenarios_dir}/{fid}/"))]
        unbound = {g["path"] for g in own_gaps if g["rule"] == "scenario.binding"}
        scenarios = []
        for sid, owner in static["scenarios"].items():
            if owner != fid:
                continue
            path = f"{scenarios_dir}/{fid}/{sid.split('.', 1)[1] if '.' in sid else sid}.json"
            data = read_json(os.path.join(root, path)) or {}
            got = query_words & words(" ".join(step_text(s) for s in data.get("steps") or []) + " " + sid)
            if got:
                matched.append({"field": f"scenario {sid}", "value": ", ".join(sorted(got)), "via": "words"})
                hit_words |= got
            scenarios.append({"id": sid, "matched": sorted(got), "bound": path not in unbound})
        score = PHRASE_WEIGHT * phrases + len(hit_words)
        if not score:
            continue
        bound = [s for s in scenarios if s["bound"]]
        limits = [g["message"] for g in own_gaps]
        if not bound:
            limits.append("no scenario with a test binding, so a feature run cannot observe this feature")
        candidates.append({"feature": fid, "score": score, "summary": record.get("summary"),
                           "knowledge": record.get("knowledge"), "sourceRoots": record.get("sourceRoots"),
                           "matched": matched, "reach": reach, "scenarios": scenarios,
                           "runnable": bool(bound) and control["state"] == "present", "limits": limits,
                           "behavior": "inferred"})
    candidates.sort(key=lambda c: (-c["score"], c["feature"]))
    candidates = candidates[:limit]

    execution = {"scope": scope, "authorized": False, "commands": [], "reason": pointer["execution"].get("reason"),
                 "guidance": pointer["execution"].get("guidance")}
    if scope == "local" and control["state"] == "present" and candidates:
        prefix = shlex.split(control["command"])
        top = candidates[0]
        term = next((m["value"] for m in top["matched"] if m["via"] in ("phrase", "literal")), None) or \
            " ".join(sorted({w for m in top["matched"] for w in m["value"].split(", ")})[:6])
        execution["authorized"] = True
        execution["commands"].append({"purpose": "discovery", "argv": prefix + ["list", "--search", term, "--json"]})
        for c in candidates[:3]:
            execution["commands"].append({"purpose": "discovery", "argv": prefix + ["describe", "feature", c["feature"], "--json"]})
        tie = [c["feature"] for c in candidates[1:] if c["score"] == top["score"]]
        if tie:
            execution["run"] = f"no feature run yet: {top['feature']} ties {', '.join(tie)}; read describe and ask which one the report means"
        elif not top["runnable"]:
            execution["run"] = f"no feature run: {top['feature']} has no bound scenario to observe"
        else:
            execution["commands"].append({"purpose": "run", "argv": prefix + ["feature", top["feature"], "--json"]})
            execution["run"] = f"run only {top['feature']}; save its stdout and exit code and read them with conform.sh evidence"
        execution["note"] = "list, describe and --plan are discovery: a successful one is never an executed check"

    doc = {"mode": "candidates", "query": query.strip(), "control": control,
           "map": {"state": map_state, "features": static["counts"]["features"], "scenarios": static["counts"]["scenarios"],
                   "gaps": [{"rule": g["rule"], "path": g["path"], "message": g["message"]} for g in gaps]},
           "candidates": candidates, "execution": execution,
           "note": "every candidate is inferred from record text; only a valid, current control report read through conform.sh evidence makes behavior observed"}
    print(json.dumps(doc, indent=2))
    return 0 if candidates else 3


raise SystemExit(main(sys.argv[1:]))
PY
