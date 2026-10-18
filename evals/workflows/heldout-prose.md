# Held-out prose-fidelity groups

[Ticket 108](https://github.com/frankieramirez/mana/issues/108) instantiates the three prose rows of the [effectiveness protocol](../../docs/specs/effectiveness-evaluation.md): `prose-exempt`, `prose-scope` and `prose-verbatim`. Each is its own source group (`sealed-prose-exempt-01`, `sealed-prose-scope-01`, `sealed-prose-verbatim-01`), split `confirmation`, with new inputs that share no sentence of 30 or more characters with the public prose evals, the semantic pilot or the focused workflow cases.

Status: frozen, with both payload inventories verified and the second review of the current freeze complete. Nothing here invokes a model.

## Layout

| Path | Who may read it |
|---|---|
| `heldout/inputs/<case>/request.md` | Candidate: the ordinary request, identical across conditions |
| `heldout/inputs/<case>/fixture/` | Candidate: the workspace product files |
| `heldout/oracles/<case>.json` | Evaluator only: contract, exact checks, fact list for the adjudicator |
| `heldout/oracles/<case>/examples/` | Evaluator only: a few known-good, valid-alternative and known-bad outputs with their expected grade, adjudication and the fact each bad one shows |
| `heldout/prose-manifest.json` | Evaluator only: source groups, hashes, allowed effects, condition routes, freeze digest and freeze history |
| `heldout/prose-review.json` | Evaluator only: author record, the current second reviewer slot and earlier review results |

Only `inputs/<case>/` may be mounted into a candidate workspace. The manifest entry carries every field the protocol names, plus `fixture_path` and `oracle_sha256`. Expected answers, source-group labels and oracle identifiers never enter the request, fixture or prompt; the isolation tests check that for every condition prompt.

## Conditions

| Condition | Payload | Prose entrypoint |
|---|---|---|
| `mana` | `skills/` at `9d1aa521974bc7c72bf9cdd676de18c09a036468`, inventory digest verified | `dispel/SKILL.md`, SHA-256 checked against the pinned revision when it is present in the checkout |
| `reference` | `pstack/` in `cursor/plugins` at `101b274dd991f694e1f7024be2157e5f3adf07de`, inventory digest verified | `skills/unslop/SKILL.md`, SHA-256 taken from the raw file at that revision; it names no supporting files |
| `none` | Empty | None |

The reference digest `d8209219…f6cc` covers 170 files. The second reviewer recomputed it from a `git archive` of `pstack/` and from a checkout at the pinned revision. The authoring session could not list that package, which is why it entered in a later freeze; the manifest records how each digest was obtained.

## Oracles

Exact checks are deterministic and conclusive. `prose-exempt` requires the fenced YAML sample to appear exactly once with its original bytes, `config/image-cache.yaml` to be unchanged and the doc to be edited. `prose-scope` requires the notes file to be unchanged. `prose-verbatim` requires the reply, after trimming surrounding whitespace, to equal Priya Raman's second answer byte for byte; text around an intact quote is `extra-text`, any other difference is `quote-altered`. All three cases check changed product paths against `allowed_effects` and fail any created commit.

No prose verdict is automatic. When an output clears the exact checks in `prose-exempt` or `prose-scope`, its outcome is `needs_adjudication` and the result carries the case's fact list. A human or model adjudicator judges the prose against that list. Each fact has an id, a kind, a statement and a review question:

- `must-survive`: a stated fact the output keeps.
- `condition`: a scope, version, trigger or example boundary the output must not lose.
- `must-not-add`: facts from the YAML sample, and reasons, mechanisms, consequences or other facts the source does not support. Restating or characterizing what the source says is allowed.
- `request`: what the request asks of the output, such as a reply shorter than the source with nothing around it.

Style is not a fidelity defect, and the tests check that style edits outside protected bytes never add an exact failure.

Each group keeps a few labeled outputs for the second reviewer. Every one names its expected grade. In the prose groups it also names the expected adjudication, `faithful` or `unfaithful`, and an unfaithful one names in `shows` the one fact it was built to show. It may break other facts too: the adjudicator judges each output against the whole list. `--check` verifies that every `shows` names a known fact. A known-bad output either fails an exact check or is unfaithful.

## Freeze and exposure

```bash
python3 -B evals/workflows/heldout_prose.py --check
python3 -B evals/workflows/heldout_prose.py --recompute
python3 -B evals/workflows/heldout_prose.py --grade prose-verbatim observation.json
python3 -B evals/workflows/heldout_prose.py --refreeze "AUTHOR" "WHAT CHANGED AND WHY" 2026-10-17
```

`--check` recomputes request, fixture and oracle digests and the `freeze_sha256` over source groups, splits, allowed effects, condition routes, payload pins and exposure. It also prints the open readiness gates. An observation for `--grade` holds `report`, the final product `files` and `commits_created`.

Changing any input, oracle, example or manifest field needs a deliberate refreeze; the tests reject stale digests. `--refreeze` recomputes the digests, appends a `history` entry chained to the previous freeze and points the review record at the new freeze. A completed review then names an older freeze, so verification asks for a new one. Oracle repairs are allowed only before outcomes exist, and each one is recorded in that history. When anyone tuning a candidate reads a group's inputs or labels, add an `exposure` record naming the group, reader, date and reason. Verification then requires that group's split to be `development`; replace it with an untouched group for confirmation.

## Review record

`prose-review.json` names the fixture author, who does not edit `skills/`, `agents/` or `output-styles/`. Its `second_review` slot is `pending`, `changes_required` or `complete`. A named result needs a reviewer other than the author, a date, the freeze it read and the four check fields; a `changes_required` result also needs notes saying what failed. Only a `complete` review of this exact freeze with every check true makes the groups ready. When a review is superseded, its record moves to `history`. Seven reviews of earlier freezes requested changes and are history entries 1 to 7. The first six each found a gap in an automated prose-fidelity screen: pattern lists, then closed lists of canonical sentences, then scare quotes. The ticket asks for oracle review, not a screen, so the screen and the labeled corpora built to test it are gone. The seventh found that the `4.2` token and word-count checks graded prose and that some labels were incomplete; those checks became facts for the adjudicator. The slot holds a `complete` review of the current freeze.

## Limits

These groups are held out from candidate tuning; they are not secret. The repository is public, so later model training could include them. The focused condition adapter still admits only `development` cases, so running these groups needs the comparative runner work that remains under build 88. The offline tests establish freeze integrity and exact-check behavior on labeled outputs; they say nothing about skill effectiveness.

```bash
python3 -B -m unittest discover -s evals/workflows -p test_heldout_prose.py
```
