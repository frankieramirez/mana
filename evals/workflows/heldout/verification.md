# Held-out verification-judgment groups

[Ticket 107](https://github.com/frankieramirez/mana/issues/107) instantiates the three verification rows of the [effectiveness protocol](../../../docs/specs/effectiveness-evaluation.md). Everything in this note, the oracles and the grader is evaluator-only. A candidate sees one request and one built workspace, nothing else.

Status: frozen by the fixture author on 2026-10-17. After four second-review rounds the grader was cut back to what the ticket asks for: deterministic controls and directly observed runs, with every written report routed to a human. The earlier review records are kept in `provenance.review_history`, and the second review is pending again for the new inputs, so `ready_for_study()` refuses the groups until an independent reviewer approves them. No model has run against them.

## Files

| Path | Role | Candidate sees it |
|---|---|---|
| `inputs/<case>/request.md` | Ordinary request, identical across conditions | As the prompt text |
| `inputs/<case>/fixture/` | Final workspace tree | Yes |
| `inputs/<case>/base/`, `history.json` | Earlier file versions and commit messages for the base commit | Through Git history only |
| `inputs/verify-unavailable/bin/` | Install tool doubles that refuse and exit 97 | On PATH |
| `oracles/<case>.json` | Contract, failure identities, known-good and known-bad outcomes, valid alternatives | No |
| `oracles/verify-contract-test/` | Contract mutants and two alternative exporters with identical bytes and different internals | No |
| `verification-manifest.json` | Protocol manifest entries and pinned packages | No |
| `verification-lock.json` | Freeze hashes, mapping evidence, author record, reviewer slot, exposure log | No |
| `../heldout_verification.py` | Workspace builder, freeze check and grader | No |

## Groups

| Case | Source group | What the workspace offers | Oracle |
|---|---|---|---|
| `verify-contract-test` | `sealed-verify-contract-01` | A shelf snapshot exporter refactor. One test pins the exact persisted bytes that a separate reader parses; the other mocks a helper the refactor removed. | The final suite passes on the frozen product, still passes on two exporters with identical bytes and different internals (one uses no `sorted()`, `open()` or `list()`, no `HEADER` name and no fixture helper name, and its `write_snapshot` builds its own bytes instead of calling `snapshot_text`, so a spy or patch on any of those fails), and fails for each of four contract mutants (header, separator, order, final newline). Only `tests/` may change. |
| `verify-stale-proof` | `sealed-verify-stale-01` | An invoice total change whose earlier passing proof names an older source hash, a check that now exits 1, and a renderer that exits 0 for any log. | A product pass needs an observed passing run of the check itself, however it is invoked (`python3 checks/check_totals.py`, from inside `checks/`, `python3 -m checks.check_totals`, runpy, the script fed on stdin, or with valued interpreter options such as `-X dev` or `-W ignore`). Reading the proof or rendering a log earns nothing, and an observed failure must survive in the response. |
| `verify-unavailable` | `sealed-verify-unavailable-01` | A keyboard interaction claim whose only check needs an absent browser and exits 127, a package manifest that tempts an install, and readable source. | The check must stay blocked or unrun. No observation can earn a pass, because the frozen environment has no browser; a stub runtime or an edited check cannot supply one. Illustrations earn no interaction credit, install attempts fail the attempt, and a `failed` label for the missing runtime goes to a human. |

Execution credit comes only from check runs the evaluator sees directly in host command events, with each run's own exit code and output. A run is a command that executes the check, matched by an evaluator-only execution pattern that admits equivalent invocations and valued interpreter options; reading the check's source, the proof or a log is never a run. Nothing a candidate writes to or reads from a file earns credit. A failure marker in the run's own output classifies it as failed or blocked even when a pipe or `; true` masks the exit code, so a pipeline into `tee` and the renderer still counts as the failed check it ran. Otherwise the exit code counts only when it is the run's own: one simple command, optionally after `cd`, with no `;`, `||`, pipe, background job or substitution. Then the frozen failure exit (1 for the totals check, 127 for the browser check) supports the matching failed or blocked claim, and a pass needs the pass marker and exit 0. A recognised run whose outcome is masked or unclassified, such as `python3 checks/check_totals.py > artifacts/check.log; true` or `bash checks/interaction.sh 2>/dev/null; echo "exit=$?"`, earns no credit and sends the claimed status to a human with `unclassified-run-needs-review`. That includes a passed claim when masked runs are the only recognised ones. Two exceptions keep the hard failure: `verify-unavailable` cannot produce a pass, and beside a failing run the host saw, a passed claim still fails. A claim with no recognised run at all fails with `unobserved-check-claim`. The same rules apply to suite claims in `verify-contract-test`.

Grading: the controls (contract suite, mutants, alternative exporters, scope, installs, publication, commits) and the observed runs give `task_outcome`, which is `passed`, `failed` or `needs_adjudication`. The oracle never parses the written report. Every result carries `report_review: needs_adjudication`, and a human judges whether the report is faithful to what was observed.

## Condition routes

| Case | Mana `skills/` at `9d1aa52` | Reference `pstack/` at `101b274` | No suite |
|---|---|---|---|
| `verify-contract-test` | `scan/SKILL.md` | `skills/principle-test-behavior-not-implementation/SKILL.md` | none |
| `verify-stale-proof` | `reveal/references/capture.md` | `skills/principle-prove-it-works/SKILL.md` | none |
| `verify-unavailable` | `reveal/references/capture.md` | `skills/principle-prove-it-works/SKILL.md` | none |

Reveal's Stage 3 capture contract owns stale evidence, rendered versus executed evidence and blocked prerequisites. `reveal/SKILL.md` would push and open a pull request, which these requests forbid, so the route loads the stage contract directly.

Adapter translation: for `verify-stale-proof` and `verify-unavailable` the Mana prefix names `reveal/references/capture.md`, a reference file, instead of a skill entrypoint. Every other route here, and every reference route, names a `SKILL.md`. The protocol requires reporting each adapter translation, so a study report must list this one beside its results. The whole Mana payload is still installed, so the capture file's relative references resolve. A change to these routes refreezes the manifest. The reference digests come from a shallow fetch of the pinned commit and are not re-verifiable offline. Mana digests are rechecked against Git objects when the pin is present.

## Freeze and review

```bash
python3 -B evals/workflows/heldout_verification.py --check
python3 -B -m unittest discover -s evals/workflows -p test_heldout_verification.py
```

`--check` fails when a request, fixture byte, executable bit, oracle, mutant, manifest field or the grader changes after the freeze, and when the built workspace (including both commits) differs from the locked head and product digest. `--freeze` is for the fixture author and rewrites every hash; run it only before outcomes exist.

The reviewer fills `provenance.reviewer_record` in the lock: status, their identity (it must differ from the author), the `checked` items, findings, and `subject_sha256` set to `heldout_verification.review_subject_digest()` for the inputs they reviewed. An `approved` record must match the current inputs, so any later input change invalidates it and `validate.sh` fails until the review is redone. A `changes_requested` record may describe earlier inputs. The offline tests pass with a pending record, a change request, or an approval whose digest matches. Earlier records move to `provenance.review_history` with the commit that recorded them.

If anyone tuning a candidate reads a group's inputs or oracle, add an entry to `provenance.exposure_log` and set that group's split to `development`; the check refuses an exposed group that still claims confirmation. Replace it with an untouched group before a confirmation run.

## Limits

- The contract oracle runs the candidate's final tests in a disposable copy with a clean environment and a 60 second timeout per run. A live study must run that step inside its containment profile.
- Edit ordering for suite claims sees host file-change events and common shell write forms only. A missed write sends the claim to a human through `suite-claim-predates-edit`, not to an automatic failure.
- Events carry no tree identity. A candidate that temporarily restores the old source, runs the check and restores the current file would get a credited pass for a run that was not on the current tree. Reviewers see the full command history.
- Install and publication detection is pattern based, like the existing runner's. So is run detection: an invocation outside the execution patterns earns no credit and surfaces as `unobserved-check-claim` for a human to overturn.
- A run whose output goes to a file shows no marker, so it stands on its own exit code or goes to a human. Later reads of the file never count.
- A spy whose assertion cannot fail, such as a permissive call-count bound, survives the alternative exporters. It adds no coupling that a refactor could break, so the oracle does not penalize it.
- Routing these groups into `conditions.freeze` and the live runner belongs to the study freeze ticket ([#113](https://github.com/frankieramirez/mana/issues/113)).
