"""POST /readings handler for sensor batches sent by field devices."""
import json
import math

import stats


def invalid_readings(readings):
    """Name the contract violation in readings, or return None."""
    if not isinstance(readings, list) or not readings:
        return "readings must be a non-empty list of numbers"
    for index, value in enumerate(readings):
        if type(value) not in (int, float) or not math.isfinite(value):
            return "readings[%d] is not a finite number" % index
    return None


def handle(body):
    """Return (status, payload) for one request body given as bytes."""
    try:
        payload = json.loads(body)
    except ValueError:
        return 400, {"error": "body is not JSON"}
    if not isinstance(payload, dict) or "readings" not in payload:
        return 400, {"error": "readings missing"}
    problem = invalid_readings(payload["readings"])
    if problem:
        return 400, {"error": problem}
    try:
        summary = stats.summarize(payload["readings"])
    except Exception as error:
        raise RuntimeError("summary failed for a validated batch") from error
    return 200, {"device": payload.get("device"), **summary}
