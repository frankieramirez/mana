#!/usr/bin/env python3
"""Advisory semantic grading of saved skill outputs, using only the stdlib."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sys
import time
import urllib.error
import urllib.request

HERE = Path(__file__).resolve().parent
ENDPOINT = "https://api.typesafe.ai/v1/systemone"


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def load_inputs(cases_path, questions_path):
    questions = read_json(questions_path)
    if not isinstance(questions, dict) or not questions:
        raise ValueError("questions must be a nonempty object")
    for key, question in questions.items():
        if not re.fullmatch(r"[a-z][a-z0-9_]*", key):
            raise ValueError("question IDs must be lowercase identifiers")
        if not isinstance(question, dict) or question.get("type") != "noul" or not question.get("instructions"):
            raise ValueError(f"{key}: expected a noul question with instructions")
    cases, seen = [], set()
    for number, line in enumerate(cases_path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        case = json.loads(line)
        if not isinstance(case, dict):
            raise ValueError(f"line {number}: expected an object")
        for field in ("id", "source", "output"):
            if not isinstance(case.get(field), str) or not case[field].strip():
                raise ValueError(f"line {number}: missing {field}")
        if not re.fullmatch(r"[a-zA-Z0-9_.-]+", case["id"]) or case["id"] in seen:
            raise ValueError(f"line {number}: invalid or duplicate id")
        seen.add(case["id"])
        expected = case.get("expected", {})
        if not isinstance(expected, dict) or any(k not in questions or type(v) is not bool for k, v in expected.items()):
            raise ValueError(f"{case['id']}: expected labels must map question IDs to booleans")
        cases.append(case)
    if not cases:
        raise ValueError("cases file is empty")
    return cases, questions


def payload(case, questions, model):
    # Labels, explanations, and IDs must never leak into the judge's context.
    return {"model": model, "state": {"source": case["source"], "output": case["output"]}, "questions": questions}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def http_error_detail(exc, key):
    """Retain the server diagnostic without logging credentials or terminal escapes."""
    try:
        text = exc.read(8192).decode("utf-8", errors="replace")
    except OSError:
        return "response body unavailable"
    text = text.replace(key, "[REDACTED]") if key else text
    text = re.sub(r"(?i)Bearer\s+[^\s\"<>]+", "Bearer [REDACTED]", text)
    text = " ".join("".join(c for c in text if c.isprintable() or c in "\n\t").split())
    return text[:2000] or "empty response body"


def ask(body, key):
    request = urllib.request.Request(ENDPOINT, data=json.dumps(body).encode(),
                                    headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    # Do not forward credentials to a redirected endpoint. No automatic retries:
    # a timeout may already have consumed tokens, so leave reruns to the caller.
    try:
        with urllib.request.build_opener(NoRedirect).open(request, timeout=30) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        with exc:
            detail = http_error_detail(exc, key)
        raise ValueError(f"Jev HTTP {exc.code}: {detail}") from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise ValueError("Jev connection failed or timed out") from None
    except (ValueError, UnicodeError):
        raise ValueError("Jev returned invalid JSON") from None


def validate_response(response, questions):
    if not isinstance(response, dict) or not isinstance(response.get("model"), str):
        raise ValueError("invalid response model")
    answers = response.get("answers")
    if not isinstance(answers, dict) or set(answers) != set(questions):
        raise ValueError("response question IDs do not match request")
    for answer in answers.values():
        if not isinstance(answer, dict):
            raise ValueError("invalid answer")
        value = answer.get("noul")
        if answer.get("type") != "noul" or type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1:
            raise ValueError("invalid noul probability")
    usage = response.get("usage")
    if not isinstance(usage, dict) or any(type(usage.get(k)) is not int or usage[k] < 0 for k in ("input_tokens", "output_tokens")):
        raise ValueError("invalid token usage")


def verdict(probability, low, high):
    return "pass" if probability <= low else "fail" if probability >= high else "uncertain"


def evaluate(case, response, low, high):
    results = {}
    for name, answer in response["answers"].items():
        decision = verdict(answer["noul"], low, high)
        expected = case.get("expected", {}).get(name)
        comparison = "unlabeled"
        if expected is not None:
            comparison = ("uncertain" if decision == "uncertain" else
                          "false-pass" if expected and decision == "pass" else
                          "false-fail" if not expected and decision == "fail" else "agree")
        results[name] = {"probability": answer["noul"], "verdict": decision,
                         "expected_violation": expected, "comparison": comparison}
    return results


def save_report(directory, report):
    (directory / "report.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    rows = ["# Semantic evaluation", "", f"Status: {report['status']}. Model requested: `{report['model']}`.",
            "", "Advisory results. A pass is a judge prediction, not proof of correctness.", "",
            "| Case | Question | P(violation) | Verdict | Compared with label |",
            "|---|---|---:|---|---|"]
    counts = {k: 0 for k in ("agree", "false-pass", "false-fail", "uncertain", "unlabeled")}
    for run in report["runs"]:
        for name, result in run["results"].items():
            counts[result["comparison"]] += 1
            rows.append(f"| {run['id']} | {name} | {result['probability']:.4f} | {result['verdict']} | {result['comparison']} |")
    rows += ["", ", ".join(f"{key}: {value}" for key, value in counts.items()), "",
             f"Completed cases: {len(report['runs'])}/{report['case_count']}.",
             f"Input tokens: {sum(r['response']['usage']['input_tokens'] for r in report['runs'])}.",
             f"Output tokens: {sum(r['response']['usage']['output_tokens'] for r in report['runs'])}.",
             f"Request time: {sum(r['seconds'] for r in report['runs']):.3f}s."]
    if report.get("error"):
        rows += ["", f"Error: {report['error']}"]
    (directory / "report.md").write_text("\n".join(rows) + "\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=HERE / "cases.jsonl")
    parser.add_argument("--questions", type=Path, default=HERE / "questions.json")
    parser.add_argument("--model", default="jev-latest", help="Jev model ID or alias (default: jev-latest)")
    parser.add_argument("--check", action="store_true", help="validate inputs without a key or network")
    parser.add_argument("--limit", type=int, help="maximum cases to send")
    parser.add_argument("--pass-at", type=float, default=0.2)
    parser.add_argument("--fail-at", type=float, default=0.8)
    parser.add_argument("--out", type=Path, help="new report directory; default: evals/results/semantic-<timestamp>")
    args = parser.parse_args(argv)
    try:
        if not 0 <= args.pass_at < args.fail_at <= 1:
            raise ValueError("thresholds must satisfy 0 <= pass-at < fail-at <= 1")
        if args.limit is not None and args.limit < 1:
            raise ValueError("limit must be positive")
        cases, questions = load_inputs(args.cases, args.questions)
        cases = cases[:args.limit]
        if args.check:
            print(f"Validated {len(cases)} cases and {len(questions)} questions; no API calls.")
            return 0
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]*", args.model):
            raise ValueError("supply a valid model ID or alias, such as jev-latest")
        key = os.environ.get("TYPESAFE_API_KEY", "").strip()
        if not key:
            raise ValueError("set TYPESAFE_API_KEY in your environment; use --check for offline validation")
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
        directory = args.out or HERE.parent / "results" / f"semantic-{stamp}"
        directory.mkdir(parents=True, exist_ok=False)
        report = {"status": "running", "model": args.model, "case_count": len(cases),
                  "created_at": stamp, "thresholds": {"pass_at": args.pass_at, "fail_at": args.fail_at},
                  "questions": questions, "cases_sha256": hashlib.sha256(args.cases.read_bytes()).hexdigest(),
                  "runs": []}
        save_report(directory, report)
        print(f"Sending {len(cases)} saved outputs to Jev. Reports: {directory}", flush=True)
        try:
            for case in cases:
                start = time.monotonic()
                response = ask(payload(case, questions, args.model), key)
                validate_response(response, questions)
                report["runs"].append({"id": case["id"], "case": case, "response": response,
                                       "seconds": round(time.monotonic() - start, 4),
                                       "results": evaluate(case, response, args.pass_at, args.fail_at)})
                save_report(directory, report)
                print(f"Graded {case['id']}", flush=True)
        except (ValueError, KeyboardInterrupt) as exc:
            report["status"] = "incomplete"
            report["error"] = str(exc) or "Interrupted"
            save_report(directory, report)
            print(f"Incomplete: {report['error']}. Partial report: {directory}", file=sys.stderr)
            return 2
        report["status"] = "complete"
        save_report(directory, report)
        print(f"Advisory report: {directory / 'report.md'}")
        return 0
    except (OSError, ValueError) as exc:
        print(f"semantic-eval: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
