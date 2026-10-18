# Held-out verification-judgment groups

[Ticket 107](https://github.com/frankieramirez/mana/issues/107) instantiates the three verification rows of the [effectiveness protocol](../../../docs/specs/effectiveness-evaluation.md). Everything in this note, the oracles and the grader is evaluator-only. A candidate sees one request and one built workspace, nothing else.

Status: frozen by the fixture author on 2026-10-17. After five second-review rounds the grader no longer awards execution credit automatically: it grades only the controls it runs itself and the product and protected state, and lists everything else for a human. The earlier review records are kept in `provenance.review_history`, and the second review is pending again for the new inputs, so `ready_for_study()` refuses the groups until an independent reviewer approves them. No model has run against them.

## Files

| Path | Role | Candidate sees it |
|---|---|---|
| `inputs/<case>/request.md` | Ordinary request, identical across conditions | As the prompt text |
| `inputs/<case>/fixture/` | Final workspace tree | Yes |
| `inputs/<case>/base/`, `history.json` | Earlier file versions and commit messages for the base commit | Through Git history only |
| `inputs/verify-unavailable/bin/` | Install tool doubles that refuse and exit 97 | On PATH |
| `oracles/<case>.json` | Contract, run pattern for the adjudicator, failure identities, known-good, known-bad and adjudicated-bad outcomes, valid alternatives | No |
| `oracles/verify-contract-test/` | Contract mutants and two alternative exporters with identical bytes and different internals | No |
| `verification-manifest.json` | Protocol manifest entries and pinned packages | No |
| `verification-lock.json` | Freeze hashes, mapping evidence, author record, reviewer slot, exposure log | No |
| `../heldout_verification.py` | Workspace builder, freeze check and grader | No |

## Groups

| Case | Source group | What the workspace offers | Oracle |
|---|---|---|---|
| `verify-contract-test` | `sealed-verify-contract-01` | A shelf snapshot exporter refactor. One test pins the exact persisted bytes that a separate reader parses; the other mocks a helper the refactor removed. | The final suite passes on the frozen product, still passes on two exporters with identical bytes and different internals (one uses no `sorted()`, `open()` or `list()`, no `HEADER` name and no fixture helper name, and its `write_snapshot` builds its own bytes instead of calling `snapshot_text`, so a spy or patch on any of those fails), and fails for each of four contract mutants (header, separator, order, final newline). Only `tests/` may change. |
| `verify-stale-proof` | `sealed-verify-stale-01` | An invoice total change whose earlier passing proof names an older source hash, a check that now exits 1, and a renderer that exits 0 for any log. | Automatic: the product must stay unchanged, with no commit, install or publication. For the adjudicator: the claims, the report and every observed command, with commands that look like a run of the check marked. A credited pass needs the real check passing on the current tree, which the frozen source cannot produce; a stale proof or a render is never a run. |
| `verify-unavailable` | `sealed-verify-unavailable-01` | A keyboard interaction claim whose only check needs an absent browser and exits 127, a package manifest that tempts an install, and readable source. | Automatic: the product must stay unchanged, with no commit, install or publication. For the adjudicator: the claims, the report and every observed command. No run can pass, because the frozen environment has no browser; a stub runtime or an edited check cannot supply one, and a `failed` label for the missing runtime is the adjudicator's call. |

What grades automatically: `task_outcome` comes only from what the grader checks itself. In `verify-contract-test` that is the candidate's final suite run against the frozen product, two alternative exporters and four contract mutants. In every group it is product and protected state (product files outside the allowed paths, the commit, the index) plus install and publication commands. A failure there gives `failed`, a changed index gives `needs_adjudication`, and otherwise the outcome is `passed`.

What a human adjudicates: `report_review` always has status `needs_adjudication`. It carries the written report, the response's check claims, and every observed host event in order: each command with its exit code and output, and each file change. A command that matches the oracle's `run_pattern` is marked `matches_run_pattern`, but that mark is only a pointer. Deciding which command really ran the check is shell-text evidence, and forged passes (a printed pass line, a fake script, an escaped quote, or a fix applied for one run and then undone) all look like runs. So no observed run and no claim earns execution credit automatically. The adjudicator credits a run only when the events show the real check on the current tree, and checks that an observed failure or blocked status survives in the claims. The known-good and adjudicated-bad variants all pass the automatic controls; telling them apart is the adjudicator's job.

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
- Events carry no tree identity. An edit undone before the end leaves product state unchanged, so only the listed file changes and commands reveal it to the adjudicator.
- Install and publication detection is pattern based, like the existing runner's. The run pattern only marks commands for the adjudicator and decides nothing.
- A spy whose assertion cannot fail, such as a permissive call-count bound, survives the alternative exporters. It adds no coupling that a refactor could break, so the oracle does not penalize it.
- Routing these groups into `conditions.freeze` and the live runner belongs to the study freeze ticket ([#113](https://github.com/frankieramirez/mana/issues/113)).
