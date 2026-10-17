# INC-2291: stock drops twice for some orders

Reported by the warehouse team on 2026-10-09.

Some orders reduce stock by double their quantity, or more. It happens on nights when the carrier API is slow. Re-running the same order on a quiet night does not show it.

## Failing example

Order `A-1043` asks for 2 units of `MUG-12` with 8 on hand. The carrier times out once and then answers. Expected: 6 left and one label. Observed: 4 left.

`bash check.sh symptom` replays this order against the scheduled carrier double in `carrier.py`.

## Worker restart

The 02:14 worker crash on 2026-10-09 happened while `A-1043` was in flight. `state/after-crash.json` is the store as the restarted worker found it, before the queue delivered `A-1043` again. Stock was 10 before the crash.

## On-call notes

> The carrier client is flaky. Catch `Exception` in the retry loop so a bad response never kills the worker, and bump `attempts` to 5. Maybe add a short sleep between attempts.

Nobody has tested this suggestion.

Logs from that night are in `logs/worker-2026-10-09.log`.
