# Challenge an installed control

Load during Challenge when local execution is authorized. The generated control belongs to the project; every discovery or run command executes project code. Static conformance alone does not authorize execution.

Start with the static checker, then use the project's `Command:` prefix to list, describe, and run the mapped feature. Validate the actual saved report with its process exit code. Run the existing dynamic checker against committed candidate bytes:

```bash
bash "<SKILL_DIR>/scripts/conform.sh" static <repo>
bash "<SKILL_DIR>/scripts/conform.sh" report <report.json> --exit <actual-code>
bash "<SKILL_DIR>/scripts/conform.sh" dynamic <repo> --trust --feature briefing --timeout <seconds>
```

The dynamic challenge runs discovery, baseline, declared failure, restoration, and concurrent executions in disposable worktrees. It excludes uncommitted changes and reports that exclusion. Inspect expected versus executed scenario ids and the failed check, not just the wrapper exit. Missing prerequisites, zero cases, source drift, timeout, cancellation, or cleanup failure must remain incomplete or cancelled as appropriate.

Use an isolated test checkout for additional negative cases. Remove a named prerequisite, arrange zero executed assertions, and mutate relevant source while a run is in progress. Preserve the original checkout's HEAD, index, tracked bytes and untracked bytes. Confirm that retained artifacts remain readable after the disposable fixture is removed.

The packaged local fixture demonstrates the generation and execution path with real assertions. It does not establish a private consumer's install, browser fixture, deployed behavior, or cold-session usability. Those require observations from that consumer and environment. Append actual challenge run ids and precise scope to the project ledger; retain prior failures. Keep a failed or blocked candidate unverified.
