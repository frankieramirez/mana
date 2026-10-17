# Prose-ablation confirmation cases

[Ticket 115](https://github.com/frankieramirez/mana/issues/115) adds the six confirmation source groups that the [instruction-ablation decision](../../docs/specs/instruction-ablations.md#first-experiment-prose-fidelity) requires for the first prose experiment. They were written after the [payload freeze](prose-ablation.md) by an evaluator who did not tune the candidate, and they are frozen against that exact payload set.

Status: frozen by the case author, second review pending. `--check` reports the open gate, and `--manifest` refuses to write a runnable study until it closes. No model has seen these inputs.

## The six groups

Each group holds one case, split `confirmation`, with a 180 second timeout.

| Group | Kind | Request in short | What a rewrite can get wrong | What it must keep |
|---|---|---|---|---|
| `pfc1-absent-cause` | absent causal explanation | Library circulation notes become a front desk notice | Inventing a reason for the shorter DVD hold, or turning the separate shelf remark into the cause | March 3, new-release DVDs at 4 days, other holds at 7 days |
| `pfc2-adjacent-config` | adjacent code/config inference trap | Clean up the prose around a dome autoclose TOML block | Moving thresholds, the rain sensor or the gust comment into prose; closing on lost contact; reopening by itself | Bad-weather close, manual close from the console, lost contact leaves the dome in place, no automatic reopen |
| `pfc3-nonexhaustive-list` | non-exhaustive list of invalid inputs | Tighten a call-for-proposals FAQ answer | Making three example checks the full list, adding a check, treating a passed form as acceptance | The three checks as examples, committee discretion, June 12 |
| `pfc4-conditional-quantity` | conditional quantitative claim | Bike-share notes become one help paragraph | Free rides for everyone or on e-bikes, a certain price change after the pilot, an invented discount | Free 30 minutes only for annual members on classic bikes, 15 and 20 cent rates, $1 unlock, undecided after September 30 |
| `pfc5-supported-explanation` | source-supported concrete explanation | Shorten a pool closure email | Replacing the stated pump failure with "maintenance", adding a cause, promising Saturday, dropping the inspection | Chlorine pump failure, part expected Thursday, inspector sign-off, Saturday as a target, kids' pool open |
| `pfc6-interpretation-verbatim` | explicit interpretation request with a verbatim segment | Keep a logrotate block and explain each line | Misreading `rotate 8` or `delaycompress`, describing directives the block lacks, inventing the team's motive | The block byte for byte, a correct reading of every line, the pointer to Imran |

None of the subjects, contracts or sentences come from the development material: the eight public dispel evals, the semantic pilot, the focused workflow cases, the held-out workflow groups, the dispel payload text, the designed debugging and comment cases, or the two historical invention cases in the changelog. `--check` enforces the text side of that rule by failing on any run of eight words a confirmation request or source shares with those files, including files added there later.

## Layout

| Path | Who may read it |
|---|---|
| `prose-confirmation/cases.json` | The ordinary request, protected spans and split for each case. Requests reach the candidate. |
| `prose-confirmation/inputs/<case>/` | Raw source files, mounted byte for byte into the candidate workspace. |
| `prose-confirmation/oracles/<group>.json` | Evaluator only: contract, source statements, legitimate alternatives, screen checks with reviewer questions, and labeled outputs. |
| `prose-confirmation/freeze.json` | Evaluator only: the lock. |
| `prose-confirmation/exposures.json` | The exposure rule and every recorded exposure. |
| `prose-confirmation/review.json` | The author record and the pending second-review slot. |

Oracle text never enters the manifest, the frozen controls or the prompt. Each oracle carries a canary string, and the checks fail if a canary appears in anything a candidate could receive.

## Freeze

`freeze.json` pins the payload set digest, the baseline revision, each arm's inventory and patch digest, each case's request digest, raw source inventory, protected span offsets and digests, and oracle digest, plus the 36-slot schedule and its digest, the exposure record digest and the development screen settings. `freeze_sha256` covers all of it.

The schedule comes from `prose_ablation.build_schedule` with seed `20261017` and two repetitions: six groups in sorted order, each a shuffled block of three conditions times two repetitions. `prose_ablation.py --freeze-study` produces the same schedule bytes from the rendered manifest, and the tests check that.

```bash
python3 -B evals/workflows/prose_confirmation.py --check
python3 -B evals/workflows/prose_confirmation.py --grade pfc-pool-closure saved-final-output.md
```

`--check` recomputes the lock from the committed files and fails on any difference, regrades every labeled output, and runs the canary and development screens. It then reports the open readiness gates. Changing an input, a request, an oracle or the exposure record needs a deliberate `--refreeze`, which also sends a completed second review back to pending.

Once every gate is closed, the run uses the existing adapter:

```bash
python3 -B evals/workflows/prose_confirmation.py --manifest /absolute/manifest.json --model REQUESTED_MODEL
python3 -B evals/workflows/prose_ablation.py --freeze-study /absolute/manifest.json --out /absolute/study
python3 -B evals/workflows/prose_confirmation.py --check-study /absolute/study
```

`--check-study` confirms that the frozen study carries the locked cases, payload digest and schedule, and that no oracle material reached it. Keep the `controls_sha256` it prints with the run record.

## Oracles and the screen

Every group has statements the rewrite must keep, failure opportunities, at least two legitimate alternatives that use different wording or structure, and at least three failing outputs. At least one failing output per group is written in clean, plain style and still fails, because the decision rules that style cannot compensate for an invented fact.

`--grade` applies an advisory screen. Protected spans are conclusive: a span missing from the output is `protected-span-lost`. The screen removes the spans before it checks prose, so block values never count as prose claims. A `preserve` check looks for the retained statement and for contradictions of it; a `forbid` check looks for a known invention. A contradiction or known invention reports `screen_fail` with a named failure. A retained statement the screen cannot find, or a cue such as `because`, reports `needs_adjudication`. Only a few required facts fail on absence, where no paraphrase can carry them without the number or name.

The screen never scores register, and its output records `style_scored: false`. `--check` regrades each labeled output after adding filler, an opener and a dash outside the protected spans, and no verdict may change. A known-good output may never screen as a failure and a known-bad output may never screen as a pass.

The screen does not decide a confirmation outcome. Two blinded reviewers judge source entailment, added claims and lost conditions with the review questions stored in each oracle, and adjudicate disagreements, as the decision requires. Style is judged separately.

## Exposure and review

Any group that anyone tuning, editing or selecting a candidate reads before the candidate is fixed becomes development material. Record the group, reader, date and reason in `exposures.json`, move the group's case to the `development` split and refreeze. Verification rejects an exposed group still marked `confirmation`, and readiness stays open until a new group of the same kind, from new subject matter, replaces it and passes the second review. The case author and the second reviewer are evaluators and do not expose a group by reading it.

`review.json` names the author, who did not tune the candidate and did not edit `skills/`, `agents/`, `output-styles/` or the payload arms. The `second_review` slot stays `pending` until a different reviewer checks that every proposed good and bad output follows from the source and request for this exact freeze. A group the reviewer cannot agree on goes in `contested_groups` and must be replaced before confirmation. Verification rejects a completed review by the author or for another freeze.

## Limits

These groups are held out from candidate tuning; they are not secret. The repository is public. The offline tests prove freeze integrity, schedule identity, oracle isolation and screen behavior on labeled outputs. They say nothing about which arm is better, and no confirmation slot has run.

```bash
python3 -B -m unittest discover -s evals/workflows -p test_prose_confirmation.py
```
