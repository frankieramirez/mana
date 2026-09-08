# Watch state and commands

Load at Stage 1. The helper reads GitHub and manages local bookkeeping. The lead agent owns the repair and bounded-wait loop. No helper command changes GitHub or starts a background watcher.

```bash
bash "<SKILL_DIR>/scripts/pr-watch.sh" snapshot auto
bash "<SKILL_DIR>/scripts/pr-watch.sh" snapshot <pr-number-or-url>
```

Pin `pr.url` from the first snapshot for every later command. Numbers and `auto` resolve through the current checkout. Derive the host and base repository from that URL for separate `gh` calls, including on fork PRs.

## Observe without consuming

| Field | Contents |
|-------|----------|
| `pr` | Native PR metadata, including state, head SHA, head repository, and mergeability |
| `checks` | Current-head check names, states, buckets, and links |
| `feedback` | Published items with `key`, `version`, `acknowledged`, and full `data` |
| `snapshot_path` | Saved JSON for this observation |
| `state_path` | Private directory containing the ledger and local report |

Evaluate items whose `acknowledged` and `data.resolved` are false, regardless of CI status. Read the full `data`, including every finding inside a bot summary. Repeated polls keep showing unhandled items. A failed fetch exits nonzero and leaves the last completed ledger intact; partial output is never evidence of an empty queue. Terminal PR snapshots skip secondary fetches, so their empty checks do not establish a final CI result.

Record the verdict and evidence before acknowledging. Fixes also require a verified push. Pass the exact key and version you evaluated:

```bash
bash "<SKILL_DIR>/scripts/pr-watch.sh" ack <pr-url> <key@version>
```

A newer observed version rejects an older acknowledgment. Return to evaluation instead of substituting the latest version merely to clear the queue. Head-only changes preserve acknowledgments; changed feedback and an observed resolved-then-reopened thread receive new versions. A close-and-reopen cycle entirely between polls may be invisible. Local history never overrides newer code evidence.

Acknowledgment is local only. A resolved thread needs no acknowledgment; resolution itself follows `feedback.md` and requires a fresh contents check.

## Reserve before acting

```bash
bash "<SKILL_DIR>/scripts/pr-watch.sh" reserve retry <pr-url> <sha>
bash "<SKILL_DIR>/scripts/pr-watch.sh" reserve fix <pr-url> <sha> <issue-key>
```

Reserve one flaky rerun per head, or one of two repairs per recurring issue, before the action. Keys use letters, digits, and `_.:@=/-`. Use a stable review identity, with a suffix for separate findings in one comment. For CI, choose a workflow/job identity plus the defect. Record the mapping in the report and reuse it when another comment or run describes the same defect.

Repair limits span commits and resumed invocations. Reserve again before a corrective edit after failed validation; validation alone costs no attempt. A new SHA gets a flaky allowance, while returning to an old SHA retains its used allowance. Failed or uncertain actions do not refund reservations.

A saved-head mismatch requires a fresh snapshot and reevaluation. The reservation checks local state; Stage 3's live check is still required before a GitHub write. Exhaustion stops attendance with the investigation and prior attempts. Never rename an issue or reset state to bypass a limit.

## State lifetime

State lives under `/tmp/ward-<uid>/`, keyed by host, base repository, and PR. A single `state.tsv` ledger records observations and spent allowances. Updates replace that file atomically. Snapshots are saved separately for evidence; an interrupted write may leave an unused snapshot but cannot partially update the ledger. Read these files as data, never source them as shell code.

Keep `report.md` beside the ledger with verdicts, issue keys, reservations, pushed commits, validation evidence, and remaining decisions. Preserve it for resumed work. Temporary storage may be cleaned by the system; if earlier state is known to be missing, reconstruct spent allowances from the report and CI history before another mutation.

Use one lead session per PR. The short operation lock protects bookkeeping, not concurrent editing. On a lock error, inspect `operation.lock/pid` and establish that its owner is gone before removing a stale lock. Preserve the ledger when recovering interrupted work or migrating an earlier state format.
