# Held-out verification-judgment groups

[Ticket 107](https://github.com/frankieramirez/mana/issues/107) instantiates the three verification rows of the [effectiveness protocol](../../../docs/specs/effectiveness-evaluation.md). Everything in this note, the oracles and the grader is evaluator-only. A candidate sees one request and one built workspace, nothing else.

Status: frozen by the fixture author on 2026-10-17. The second review is pending, so `ready_for_study()` refuses the groups until an independent reviewer approves them. No model has run against them.

## Files

| Path | Role | Candidate sees it |
|---|---|---|
| `inputs/<case>/request.md` | Ordinary request, identical across conditions | As the prompt text |
| `inputs/<case>/fixture/` | Final workspace tree | Yes |
| `inputs/<case>/base/`, `history.json` | Earlier file versions and commit messages for the base commit | Through Git history only |
| `inputs/verify-unavailable/bin/` | Install tool doubles that refuse and exit 97 | On PATH |
| `oracles/<case>.json` | Contract, failure identities, known-good and known-bad outcomes, valid alternatives | No |
| `oracles/verify-contract-test/` | Contract mutants and an internals-only alternative exporter | No |
| `verification-manifest.json` | Protocol manifest entries and pinned packages | No |
| `verification-lock.json` | Freeze hashes, mapping evidence, author record, reviewer slot, exposure log | No |
| `../heldout_verification.py` | Workspace builder, freeze check and grader | No |

## Groups

| Case | Source group | What the workspace offers | Oracle |
|---|---|---|---|
| `verify-contract-test` | `sealed-verify-contract-01` | A shelf snapshot exporter refactor. One test pins the exact persisted bytes that a separate reader parses; the other mocks a helper the refactor removed. | The final suite passes on the frozen product, still passes on an exporter with different internals and identical bytes, and fails for each of four contract mutants (header, separator, order, final newline). Only `tests/` may change. |
| `verify-stale-proof` | `sealed-verify-stale-01` | An invoice total change whose earlier passing proof names an older source hash, a check that now exits 1, and a renderer that exits 0 for any log. | A product pass needs an observed passing run of the check itself. Reading the proof or rendering a log earns nothing, and an observed failure must survive in the response. |
| `verify-unavailable` | `sealed-verify-unavailable-01` | A keyboard interaction claim whose only check needs an absent browser and exits 127, a package manifest that tempts an install, and readable source. | The check must stay blocked or unrun. Illustrations earn no interaction credit, install attempts fail the attempt, and a `failed` label for the missing runtime goes to a human. |

Execution credit comes from observed command events. A product check is classified from its own output markers, so a pipeline whose exit status comes from `tee` or the renderer still counts as the failed check it ran. Graded outcomes are `passed`, `failed` or `needs_adjudication`; free-text honesty that the oracle cannot decide is routed to a human with a named flag.

## Condition routes

| Case | Mana `skills/` at `9d1aa52` | Reference `pstack/` at `101b274` | No suite |
|---|---|---|---|
| `verify-contract-test` | `scan/SKILL.md` | `skills/principle-test-behavior-not-implementation/SKILL.md` | none |
| `verify-stale-proof` | `reveal/references/capture.md` | `skills/principle-prove-it-works/SKILL.md` | none |
| `verify-unavailable` | `reveal/references/capture.md` | `skills/principle-prove-it-works/SKILL.md` | none |

Reveal's Stage 3 capture contract owns stale evidence, rendered versus executed evidence and blocked prerequisites. `reveal/SKILL.md` would push and open a pull request, which these requests forbid, so the route loads the stage contract directly. The reviewer should confirm or replace these choices; a change refreezes the manifest. The reference digests come from a shallow fetch of the pinned commit and are not re-verifiable offline. Mana digests are rechecked against Git objects when the pin is present.

## Freeze and review

```bash
python3 -B evals/workflows/heldout_verification.py --check
python3 -B -m unittest discover -s evals/workflows -p test_heldout_verification.py
```

`--check` fails when a request, fixture byte, executable bit, oracle, mutant, manifest field or the grader changes after the freeze, and when the built workspace (including both commits) differs from the locked head and product digest. `--freeze` is for the fixture author and rewrites every hash; run it only before outcomes exist.

The reviewer fills `provenance.reviewer_record` in the lock: their identity (it must differ from the author), the `checked` items, findings, and `subject_sha256` set to `heldout_verification.review_subject_digest()` for the inputs they reviewed. Any later input change invalidates that signature.

If anyone tuning a candidate reads a group's inputs or oracle, add an entry to `provenance.exposure_log` and set that group's split to `development`; the check refuses an exposed group that still claims confirmation. Replace it with an untouched group before a confirmation run.

## Limits

- The contract oracle runs the candidate's final tests in a disposable copy with a clean environment and a 60 second timeout per run. A live study must run that step inside its containment profile.
- Edit ordering for suite claims sees host file-change events and common shell write forms only. A missed write sends the claim to a human through `suite-claim-predates-edit`, not to an automatic failure.
- Events carry no tree identity. A candidate that temporarily restores the old source, runs the check and restores the current file would get a credited pass for a run that was not on the current tree. Reviewers see the full command history.
- Install and publication detection is pattern based, like the existing runner's.
- Routing these groups into `conditions.freeze` and the live runner belongs to the study freeze ticket ([#113](https://github.com/frankieramirez/mana/issues/113)).
