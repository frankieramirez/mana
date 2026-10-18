# Held-out prose-fidelity groups

[Ticket 108](https://github.com/frankieramirez/mana/issues/108) instantiates the three prose rows of the [effectiveness protocol](../../docs/specs/effectiveness-evaluation.md): `prose-exempt`, `prose-scope` and `prose-verbatim`. Each is its own source group (`sealed-prose-exempt-01`, `sealed-prose-scope-01`, `sealed-prose-verbatim-01`), split `confirmation`, with new inputs that share no sentence of 30 or more characters with the public prose evals, the semantic pilot or the focused workflow cases.

Status: frozen, with both payload inventories verified. Four review rounds each requested changes. The author repaired the oracles every time before any outcome existed and refroze. The current freeze still needs a new review, so these groups cannot enter a confirmation run yet. Nothing here invokes a model.

## Layout

| Path | Who may read it |
|---|---|
| `heldout/inputs/<case>/request.md` | Candidate: the ordinary request, identical across conditions |
| `heldout/inputs/<case>/fixture/` | Candidate: the workspace product files |
| `heldout/oracles/<case>.json` | Evaluator only: contract, exact checks, fact screens, reviewer questions |
| `heldout/oracles/<case>/examples/` | Evaluator only: labeled known-good, known-bad, valid-alternative, ambiguous and adjudicate outcomes |
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

Exact checks are deterministic and conclusive. `prose-exempt` requires the fenced YAML sample to appear exactly once with its original bytes, `config/image-cache.yaml` to be unchanged and the doc to be edited. `prose-scope` requires the notes file to be unchanged, the reply to be shorter than the source paragraph and the token `4.2` to appear, since no paraphrase can carry the version condition without it. `prose-verbatim` requires the reply, after trimming surrounding whitespace, to equal Priya Raman's second answer byte for byte; text around an intact quote is `extra-text`, any other difference is `quote-altered`. All three cases check changed product paths against `allowed_effects` and fail any created commit.

Prose screens use closed lists instead of pattern lists. Four review rounds showed that every added verb closed the tested phrasing and left its neighbours open, so the screen no longer tries to recognise meaning:

- A sentence passes only when it matches a canonical faithful statement in the oracle, after case, spacing, list markers, code ticks, quote style and end punctuation are normalized. Each canonical statement names the facts it carries.
- A sentence fails only when it matches a canonical contradiction, and a canonical contradiction may hold no negation, quantifier or reason clause. The grader refuses an oracle that breaks this rule. A negated, qualified or reworded contradiction therefore reaches a reviewer and never hard-fails faithful text.
- Any other sentence that mentions a check's topic goes to `needs_adjudication`. Failure words do not exempt a sentence. For `prose-exempt` the topics cover restart, cold, empty, survive, persist, stay, still there, carried over, full, evict, pushed aside, older, oldest and drop, plus thumbnails, the sweep, sample numbers and settings, and reasons or consequences. For `prose-scope` they cover posted_on, future dates, reject, example, only, the validation scope, the version, exclusion and the report, modification, and added facts.
- A required fact that no canonical statement carries also goes to a reviewer.

Most faithful rewrites therefore reach a reviewer, which is intended: the screen's job is to never pass an unfaithful reply and never fail a faithful one. The reviewer questions stored with each fact frame that judgment.

The screens do not score register. No topic or canonical sentence mentions dashes, filler or other style rules. The tests apply dash, filler and opener edits outside protected bytes to every labeled example except the deliberately unedited doc: no edit creates a failure, and no reply that did not pass starts passing.

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

`prose-review.json` names the fixture author, who does not edit `skills/`, `agents/` or `output-styles/`. Its `second_review` slot is `pending`, `changes_required` or `complete`. A named result needs a reviewer other than the author, a date, the freeze it read and the four check fields; a `changes_required` result also needs notes saying what failed. Only a `complete` review of this exact freeze with every check true makes the groups ready. When a review is superseded, its record moves to `history`. The first review requested changes against freeze `a9689245…9eba`; its eight defects now have regression examples (`r1` to `r6` in `prose-exempt` and `prose-scope`), and its record is history entry 1. The re-review of freeze `9f40b4cc…5ecc` requested changes for negated cold-start statements and for a failing example placed inside the success scope. That record is history entry 2, and examples `r7` to `r10` (`prose-exempt`) and `r7` to `r9` (`prose-scope`) reproduce both defects. The third review of freeze `f6afdd62…54aa` found that added verbs closed only the tested phrasings; that record is history entry 3, and examples `r11` to `r17` (`prose-exempt`) and `r10` to `r13` (`prose-scope`) cover it. The fourth review of freeze `80775510…fbba` found the same pattern again and led to the closed-list policy above. Its record stays in the `second_review` slot. Its twelve outputs are examples `r18` to `r23` (`prose-exempt`) and `r14` to `r19` (`prose-scope`), and `c1` to `c4` exercise the canonical contradictions. Examples labeled `adjudicate` must reach a reviewer. Under the new policy many earlier examples that passed or failed now reach a reviewer instead; the tests check that faithful reviewer outputs never fail and unfaithful ones never pass.

## Limits

These groups are held out from candidate tuning; they are not secret. The repository is public, so later model training could include them. The focused condition adapter still admits only `development` cases, so running these groups needs the comparative runner work that remains under build 88. The offline tests establish freeze integrity and oracle behavior on labeled outcomes; they say nothing about skill effectiveness.

```bash
python3 -B -m unittest discover -s evals/workflows -p test_heldout_prose.py
```
