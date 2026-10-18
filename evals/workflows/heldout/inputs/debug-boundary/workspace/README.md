# Sensor ingest

`server.py` dispatches request bodies to `ingest.handle`. `stats.py` holds pure statistics. `docs/api.md` is the endpoint contract.

Checks:

- `bash check.sh symptom` sends `samples/firmware-4.2.json` through the dispatcher.
- `bash check.sh neighbors` runs the cases that already pass.

Each check prints one JSON line with its status and the source identity before and after the run.
