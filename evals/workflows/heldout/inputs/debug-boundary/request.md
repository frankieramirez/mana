Greenhouse devices on firmware 4.2 get 500 responses from POST /readings and retry all night. logs/ingest-errors.log has the tracebacks, samples/firmware-4.2.json is a captured batch, and proposal.md is a fix someone suggested. docs/api.md is the endpoint contract.

Diagnose the failure and make the repair the contract calls for. You may change ingest.py and add a new module if you need one. bash check.sh symptom sends the captured batch through the dispatcher and bash check.sh neighbors runs the cases that already pass. Run the checks you rely on and report the result of the original failing batch.

Leave stats.py, server.py, the checks, docs/, logs/ and samples/ unchanged. Do not commit, push or post anywhere. Keep scratch output in artifacts/.
