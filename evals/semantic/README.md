# Semantic eval pilot

Grade saved skill outputs with Jev. This is a maintainer experiment; installed skills do not call Jev. Python 3.10+ and the standard library are sufficient.

## Run

From the repository root, validate the dataset offline:

```bash
python3 evals/semantic/run.py --check
```

Set `TYPESAFE_API_KEY` in your environment. The live command sends each selected case's source and output, plus the rubric, to TypeSafe. The default model is the documented `jev-latest` alias:

```bash
python3 evals/semantic/run.py --limit 1
python3 evals/semantic/run.py
```

Use `--model MODEL_ID` to select a model available in your account. For repeatable comparisons, use a fixed version once the provider confirms its ID. The latest alias may change over time; reports preserve both requested and returned model names, although the provider may return an alias rather than a resolved version.

Each case uses one API call containing both questions. There are no automatic retries. A request times out after 30 seconds; HTTP errors stop the run and preserve completed results. A rerun starts over and can incur charges again. `--limit` bounds the number of requests.

Reports land in an ignored, unique directory under `evals/results/`. `report.md` lists every judgment and disagreement. `report.json` preserves the inputs, rubric, requested and returned model names, raw responses, latency, and token usage. No credential is written. Token usage is recorded instead of estimating charges from a price that can change.

Use `--out /path/to/new-directory` to choose a destination. Existing directories are never overwritten. Exit 0 means the run completed, including when the judge flags failures. Exit 2 means invalid configuration or an incomplete run. The pilot is advisory and has no live CI gate.

## What the numbers mean

Both questions ask whether a violation exists. `true` in an expected label means the output is flawed on that dimension.

- Probability at or below 0.2: pass.
- Probability at or above 0.8: fail.
- Between those thresholds: uncertain.

A false pass accepts a labeled violation. A false fail rejects a labeled good output. Uncertain judgments remain separate from agreements. Unlabeled outputs receive verdicts but do not count as calibration evidence. These are provisional thresholds, configurable through `--pass-at` and `--fail-at`. Noul probabilities are not the separate confidence statistic returned by Jev's Choice and Score primitives.

The 12 checked-in cases are synthetic seed examples with agent-authored expected labels and notes. Review their labels before treating them as ground truth. They test additions and meaning loss, including unsupported causal explanations, changes to measurement scope, and facts imported from exempt code. They do not establish accuracy or cover the whole prose skill.

## Evaluate a changed skill

This runner grades saved outputs; it does not execute skills. Run the edited skill in your normal agent environment using a source request, then save its final response as `output` in a JSONL record:

```json
{"id":"my-run-1","source":"Rewrite concisely: The migration may reduce latency.","output":"The migration reduces latency."}
```

Then run:

```bash
python3 evals/semantic/run.py --cases evals/results/my-outputs.jsonl
```

Add an optional `expected` object with boolean labels for `unsupported_claim` and `meaning_lost` when a person has reviewed the case. Optional `label_note` explains the label. Neither field goes to Jev. IDs must be unique and use letters, numbers, periods, underscores, or hyphens. Source must include the original task instructions as well as the text being edited, so the judge knows which facts must survive.

Keep exact preservation checks and existing regex graders. This runner does not execute the original eval harness or replace its grades. In particular, `pr-invented-purpose` illustrates wording the current PR rationale regex misses, while `rotation-supported` illustrates a legitimate source fact the same regex would reject. Compare results with those graders separately when deciding whether the semantic judge adds value.

Before adopting any gate, expand to 50 to 100 reviewed cases, reserve source scenarios that are never used for rubric tuning, and measure false passes and false failures on that held-out set. Keep variants of one source in the same split. Repeat runs to measure judgment stability: the changelog records that earlier LLM judges fluctuated on substantively equivalent wording. Never optimize a rubric against the held-out answers.

## Offline tests

```bash
python3 -B -m unittest discover -s evals/semantic -p 'test_*.py'
```

The repository validator runs these tests without a key. Mocked responses verify reporting and failure handling; they provide no evidence of Jev's grading quality.

API contract: [TypeSafe HTTP reference](https://docs.typesafe.ai/api). Model availability: [TypeSafe models](https://docs.typesafe.ai/models). Verified API shape on 2026-09-17.

## Pilot findings

See [findings.md](findings.md) for the measured results and why this remains an optional experiment.
