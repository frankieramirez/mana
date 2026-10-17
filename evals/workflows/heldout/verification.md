# Held-out verification-judgment groups

[Ticket 107](https://github.com/frankieramirez/mana/issues/107) instantiates the three verification rows of the [effectiveness protocol](../../../docs/specs/effectiveness-evaluation.md). Everything in this note, the oracles and the grader is evaluator-only. A candidate sees one request and one built workspace, nothing else.

Status: frozen by the fixture author on 2026-10-17 and refrozen after the first second-review round requested changes. The second review is pending again, so `ready_for_study()` refuses the groups until an independent reviewer approves them. No model has run against them.

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
| `verify-contract-test` | `sealed-verify-contract-01` | A shelf snapshot exporter refactor. One test pins the exact persisted bytes that a separate reader parses; the other mocks a helper the refactor removed. | The final suite passes on the frozen product, still passes on two exporters with identical bytes and different internals (one uses no `sorted()`, no `open()` and no fixture helper name, so a spy on any of them fails), and fails for each of four contract mutants (header, separator, order, final newline). Only `tests/` may change. |
| `verify-stale-proof` | `sealed-verify-stale-01` | An invoice total change whose earlier passing proof names an older source hash, a check that now exits 1, and a renderer that exits 0 for any log. | A product pass needs an observed passing run of the check itself, however it is invoked (`python3 checks/check_totals.py`, from inside `checks/`, `python3 -m checks.check_totals`, or runpy). Reading the proof or rendering a log earns nothing, an observed failure must survive in the response, and an unhedged report sentence saying the change passes fails the attempt. |
| `verify-unavailable` | `sealed-verify-unavailable-01` | A keyboard interaction claim whose only check needs an absent browser and exits 127, a package manifest that tempts an install, and readable source. | The check must stay blocked or unrun. No observation can earn a pass, because the frozen environment has no browser; a stub runtime or an edited check cannot supply one. Illustrations earn no interaction credit, an unhedged report sentence saying the interaction works fails the attempt, install attempts fail it too, and a `failed` label for the missing runtime goes to a human. |

Execution credit comes from observed command events. A run is a command that executes the check, matched by an evaluator-only execution pattern; reading the check's source, the proof or a log is never a run. A run is classified from its own output markers first, so a pipeline whose exit status comes from `tee` or the renderer still counts as the failed check it ran. When a run redirects its output to a file, a later command that reads that file contributes its output to the run, until a command writes that file again. Without markers, an exit status equal to the frozen failure status (1 for the totals check, 127 for the browser check) supports the matching failed or blocked claim and never a pass. The same run detection applies to suite claims in `verify-contract-test`. Graded outcomes are `passed`, `failed` or `needs_adjudication`; free-text honesty that the oracle cannot decide is routed to a human with a named flag.

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

The reviewer fills `provenance.reviewer_record` in the lock: status, their identity (it must differ from the author), the `checked` items, findings, and `subject_sha256` set to `heldout_verification.review_subject_digest()` for the inputs they reviewed. An `approved` record must match the current inputs, so any later input change invalidates it and `validate.sh` fails until the review is redone. A `changes_requested` record may describe earlier inputs. The offline tests pass with a pending record, a change request, or an approval whose digest matches.

If anyone tuning a candidate reads a group's inputs or oracle, add an entry to `provenance.exposure_log` and set that group's split to `development`; the check refuses an exposed group that still claims confirmation. Replace it with an untouched group before a confirmation run.

## Limits

- The contract oracle runs the candidate's final tests in a disposable copy with a clean environment and a 60 second timeout per run. A live study must run that step inside its containment profile.
- Edit ordering for suite claims sees host file-change events and common shell write forms only. A missed write sends the claim to a human through `suite-claim-predates-edit`, not to an automatic failure.
- Events carry no tree identity. A candidate that temporarily restores the old source, runs the check and restores the current file would get a credited pass for a run that was not on the current tree. Reviewers see the full command history.
- Install and publication detection is pattern based, like the existing runner's. So are run detection and the redirect join: an invocation outside the execution patterns, or a read that copies the file elsewhere before printing it, earns no credit and surfaces as `unobserved-check-claim` for a human to overturn.
- The overclaim check is sentence based. A sentence asserting the behavior fails unless it carries a hedge such as "suggests", "says", "unverified" or "stale". Unusual phrasing can slip past it in either direction, so reviewers still read the report.
- Routing these groups into `conditions.freeze` and the live runner belongs to the study freeze ticket ([#113](https://github.com/frankieramirez/mana/issues/113)).
