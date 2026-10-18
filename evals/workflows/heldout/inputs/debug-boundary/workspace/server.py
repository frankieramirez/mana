"""Tiny dispatcher used in production and by the local checks.

An exception escaping a handler is logged with its traceback and answered with
500. Those tracebacks are how we find bugs in our own code.
"""
import json
import traceback

import ingest


def dispatch(body, log):
    try:
        status, payload = ingest.handle(body)
    except Exception:
        log.append(traceback.format_exc())
        return 500, {"error": "internal error"}
    return status, json.loads(json.dumps(payload))
