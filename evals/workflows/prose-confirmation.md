# Prose-ablation confirmation cases

[Ticket 115](https://github.com/frankieramirez/mana/issues/115) adds the six confirmation source groups that the [instruction-ablation decision](../../docs/specs/instruction-ablations.md#first-experiment-prose-fidelity) requires for the first prose experiment. They were written after the [payload freeze](prose-ablation.md) by an evaluator who did not tune the candidate, and they are frozen against that exact payload set.

Status: second review complete for the current freeze, with no contested group. The first review contested `pfc2-adjacent-config` and `pfc4-conditional-quantity` on one mislabeled valid output each. Both labels were fixed, and `review.json` keeps that review and its resolution in `history`. `--check` now reports no open gate. No model has seen these inputs, and no confirmation slot has run.

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
| `prose-confirmation/oracles/<group>.json` | Evaluator only: contract, supported facts, invented facts that fail, legitimate alternatives, adjudication questions, and a handful of labeled outputs. |
| `prose-confirmation/freeze.json` | Evaluator only: the lock. |
| `prose-confirmation/exposures.json` | The exposure rule and every recorded exposure. |
| `prose-confirmation/review.json` | The author record, the current second-review slot, and every earlier second review with its resolution. |

Oracle text never enters the manifest, the frozen controls or the prompt. Each oracle carries a canary string, and the checks fail if a canary appears in anything a candidate could receive.

## Freeze

`freeze.json` pins the payload set digest, the baseline revision, each arm's inventory and patch digest, each case's request digest, raw source inventory, protected span offsets and digests, and oracle digest, plus the 36-slot schedule and its digest, the exposure record digest and the development screen settings. `freeze_sha256` covers all of it.

The schedule comes from `prose_ablation.build_schedule` with seed `20261017` and two repetitions: six groups in sorted order, each a shuffled block of three conditions times two repetitions. `prose_ablation.py --freeze-study` produces the same schedule bytes from the rendered manifest, and the tests check that.

```bash
python3 -B evals/workflows/prose_confirmation.py --check
python3 -B evals/workflows/prose_confirmation.py --grade pfc-kiosk-logrotate saved-final-output.md
```

`--check` recomputes the lock from the committed files and fails on any difference, rechecks every oracle and the protected spans in its labeled outputs, and runs the canary and development screens. It then reports the open readiness gates. Changing an input, a request, an oracle or the exposure record needs a deliberate `--refreeze`. A refreeze moves a completed second review into `history`, with the text passed as `--resolution`, and sends the slot back to pending.

Once every gate is closed, the run uses the existing adapter:

```bash
python3 -B evals/workflows/prose_confirmation.py --manifest /absolute/manifest.json --model REQUESTED_MODEL
python3 -B evals/workflows/prose_ablation.py --freeze-study /absolute/manifest.json --out /absolute/study
python3 -B evals/workflows/prose_confirmation.py --check-study /absolute/study
```

`--check-study` confirms that the frozen study carries the locked cases, payload digest and schedule, and that no oracle material reached it. Keep the `controls_sha256` it prints with the run record.

## Oracles and grading

Each oracle is a fact list for the adjudicator:

- `supported_facts`: what the source states, which a rewrite may keep.
- `invented_facts_that_fail`: concrete claims that fail the group, such as a reason the source never gives.
- `legitimate_alternatives`: different wording or structure that still passes.
- `judgments`: the adjudication questions, one per fact to keep or failure opportunity.

Each group also carries a handful of labeled outputs: at least two valid rewrites and at least three failing ones. At least one failing output per group is written in clean, plain style and still fails, because the decision rules that style cannot compensate for an invented fact. Each failing output names in `shows` the one question it was built to show, or `protected-span-lost`. An example may fail other questions too: `shows` is not a complete list, and the adjudicator judges every output against the whole list of questions. `--check` confirms that `shows` names a known question and that each label agrees with the output's protected-span bytes.

`--grade` makes one deterministic check through the prose adapter's `protected_span_checks`. Each protected span is either present byte for byte or lost, and a lost span fails the output with exit status 1. The prose then goes to adjudication against the oracle, and `--grade` prints the oracle's facts and questions for that purpose. It never prints a prose verdict. Two blinded reviewers judge source entailment, added claims and lost conditions, and adjudicate disagreements, as the decision requires. Style is judged separately.

## Exposure and review

Any group that anyone tuning, editing or selecting a candidate reads before the candidate is fixed becomes development material. Record the group, reader, date and reason in `exposures.json`, move the group's case to the `development` split and refreeze. Verification rejects an exposed group still marked `confirmation`, and readiness stays open until a new group of the same kind, from new subject matter, replaces it and passes the second review. The case author and the second reviewer are evaluators and do not expose a group by reading it.

`review.json` names the author, who did not tune the candidate and did not edit `skills/`, `agents/`, `output-styles/` or the payload arms. The `second_review` slot stays `pending` until a different reviewer checks that every proposed good and bad output follows from the source and request for this exact freeze. A group the reviewer cannot agree on goes in `contested_groups` and must be replaced or corrected and reviewed again before confirmation. Every contested name must be one of the six group ids. Verification rejects a completed review by the author or for another freeze, and a past review in `history` that names the current freeze.

## Limits

These groups are held out from candidate tuning; they are not secret. The repository is public. The offline tests prove freeze integrity, schedule identity, oracle isolation, oracle structure and protected-span checks. They say nothing about which arm is better, and no confirmation slot has run.

```bash
python3 -B -m unittest discover -s evals/workflows -p test_prose_confirmation.py
```
