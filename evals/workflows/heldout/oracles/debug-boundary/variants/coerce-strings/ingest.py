"""POST /readings handler for sensor batches sent by field devices."""
import json

import stats


def handle(body):
    """Return (status, payload) for one request body given as bytes."""
    try:
        payload = json.loads(body)
    except ValueError:
        return 400, {"error": "body is not JSON"}
    if not isinstance(payload, dict) or "readings" not in payload:
        return 400, {"error": "readings missing"}
    try:
        readings = [float(v) for v in payload["readings"]]
    except (TypeError, ValueError):
        return 400, {"error": "readings must be numbers"}
    if not readings:
        return 400, {"error": "readings must not be empty"}
    summary = stats.summarize(readings)
    return 200, {"device": payload.get("device"), **summary}
