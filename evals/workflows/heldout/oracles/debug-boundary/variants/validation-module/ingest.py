"""POST /readings handler for sensor batches sent by field devices."""
import json

import stats
from validation import readings_error


def handle(body):
    """Return (status, payload) for one request body given as bytes."""
    try:
        payload = json.loads(body)
    except ValueError:
        return 400, {"error": "body is not JSON"}
    if not isinstance(payload, dict) or "readings" not in payload:
        return 400, {"error": "readings missing"}
    error = readings_error(payload["readings"])
    if error is not None:
        return 400, {"error": error}
    summary = stats.summarize(payload["readings"])
    return 200, {"device": payload.get("device"), **summary}
