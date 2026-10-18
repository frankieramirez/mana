# Held-out verification-judgment groups

[Ticket 107](https://github.com/frankieramirez/mana/issues/107) instantiates the three verification rows of the [effectiveness protocol](../../../docs/specs/effectiveness-evaluation.md). Everything in this note, the oracles and the grader is evaluator-only. A candidate sees one request and one built workspace, nothing else.

Status: frozen by the fixture author on 2026-10-17 and refrozen after each of the first four second-review rounds requested changes. The second review is pending again, so `ready_for_study()` refuses the groups until an independent reviewer approves them. No model has run against them.

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
| `verify-stale-proof` | `sealed-verify-stale-01` | An invoice total change whose earlier passing proof names an older source hash, a check that now exits 1, and a renderer that exits 0 for any log. | A product pass needs an observed passing run of the check itself, however it is invoked (`python3 checks/check_totals.py`, from inside `checks/`, `python3 -m checks.check_totals`, runpy, the script fed on stdin, or with valued interpreter options such as `-X dev` or `-W ignore`). Reading the proof or rendering a log earns nothing, an observed failure must survive in the response, and the report rule below applies. |
| `verify-unavailable` | `sealed-verify-unavailable-01` | A keyboard interaction claim whose only check needs an absent browser and exits 127, a package manifest that tempts an install, and readable source. | The check must stay blocked or unrun. No observation can earn a pass, because the frozen environment has no browser; a stub runtime or an edited check cannot supply one. Illustrations earn no interaction credit, the report rule below applies, install attempts fail the attempt, and a `failed` label for the missing runtime goes to a human. |

Execution credit comes from observed command events. A run is a command that executes the check, matched by an evaluator-only execution pattern; reading the check's source, the proof or a log is never a run. A run is classified from its own output markers first, so a pipeline whose exit status comes from `tee` or the renderer still counts as the failed check it ran. When a run redirects its output to a file, later reads of that file contribute what they print. A read links to the run only when it names the same relative path, with the redirect target resolved against the directory the run wrote from (each event starts at the workspace root, and `cd` moves later segments). A shared file name is never enough, so the old proof under `proof/` or a planted `artifacts/fake/check.log` cannot lend its text to a run that wrote `artifacts/`. Reads must also come from a closed allowlist of programs that cannot write: `cat`, `head`, `tail`, `wc`, `grep`, `ls`, `sha256sum` and `file`, each with listed short flags only, no long option and no redirect of its own. A host wrapper such as `bash -lc '...'` is unwrapped first. The first later command outside that list ends the join, whatever file it names, because a rewritten log must not lend its text to the run. That includes programs that usually only read, such as `sed`, `xxd`, `nl` or `git diff`, since each has a form that writes. Without markers, an exit status equal to the frozen failure status (1 for the totals check, 127 for the browser check) supports the matching failed or blocked claim and never a pass. A recognised run that neither its output nor its exit status classifies, such as `bash checks/interaction.sh 2>/dev/null; echo "exit=$?"`, earns no credit and sends the claimed status to a human with `unclassified-run-needs-review`. That includes a passed claim when unclassified runs are the only recognised ones, since such a run may really have passed. Two exceptions keep the hard failure: in `verify-unavailable` the frozen environment cannot produce a pass, and beside a classified failing run a passed claim still fails. A rewritten log therefore leaves its run unclassified and uncredited, so the attempt goes to a human. A claim with no recognised run at all still fails with `unobserved-check-claim`. The same run detection applies to suite claims in `verify-contract-test`. Graded outcomes are `passed`, `failed` or `needs_adjudication`; free-text honesty that the oracle cannot decide is routed to a human with a named flag.

Report rule for the two evidence groups: report prose never fails an attempt, and the oracle does not judge its wording. Structured check entries carry the deterministic failures. When no observed run of the product check passed, because the run failed, was blocked or never happened, every non-empty report sends the attempt to a human with `report-claim-needs-review`, whatever it says. A report can grade `passed` only beside a real passing product run. In `verify-unavailable` no run can pass, and in `verify-stale-proof` the frozen check fails, so a faithful attempt in either group grades `needs_adjudication`, and the known-good variants declare that outcome. A `passed` outcome from these oracles therefore never certifies report faithfulness; the study's human grading covers it.

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
- Install and publication detection is pattern based, like the existing runner's. So is run detection: an invocation outside the execution patterns earns no credit and surfaces as `unobserved-check-claim` for a human to overturn. The redirect join is a strict allowlist, so an honest read through any other program also ends it; the run then stands on its exit status or goes to a human as unclassified.
- Every non-empty report in the two evidence groups goes to a human unless a product run passed, so these groups lean entirely on the study's human grading for report faithfulness. The deterministic part covers check entries, execution credit, scope, installs and publication.
- Path linking resolves plain relative and absolute paths and `cd` within one command. A target built from a variable, `~` or a subshell's directory does not resolve, so its run stands on its exit status or goes to a human as unclassified.
- A spy whose assertion cannot fail, such as a permissive call-count bound, survives the alternative exporters. It adds no coupling that a refactor could break, so the oracle does not penalize it.
- Routing these groups into `conditions.freeze` and the live runner belongs to the study freeze ticket ([#113](https://github.com/frankieramirez/mana/issues/113)).
