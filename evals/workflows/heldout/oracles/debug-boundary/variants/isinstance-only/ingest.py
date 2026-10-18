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
    readings = payload["readings"]
    if not isinstance(readings, list) or not readings or not all(isinstance(v, (int, float)) for v in readings):
        return 400, {"error": "readings must be a non-empty list of numbers"}
    summary = stats.summarize(payload["readings"])
    return 200, {"device": payload.get("device"), **summary}
