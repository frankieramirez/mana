# Prose instruction-ablation payloads

[Ticket 114](https://github.com/frankieramirez/mana/issues/114) freezes the three dispel payloads for the first experiment in the [instruction-ablation decision](../../docs/specs/instruction-ablations.md#first-experiment-prose-fidelity) and adds the adapter that runs them. The payloads are evaluation material only. Nothing under `skills/` changes, and the installed dispel skill keeps its current Fidelity section and self-check item 9.

No model has run any of these payloads. The six confirmation source groups belong to [ticket 115](https://github.com/frankieramirez/mana/issues/115), which must be authored after this freeze; this change adds no confirmation case. Those groups now live in [prose-ablation confirmation cases](prose-confirmation.md).

## The frozen payload set

`prose-ablation/` holds the set. `payloads.json` records the audit baseline revision `9d1aa521974bc7c72bf9cdd676de18c09a036468`, the source inventory of `skills/dispel` at that revision, the candidate text, the selected line ranges, and for each arm its complete inventory, inventory digest and patch digest.

| Arm | Directory | Change from the baseline |
|---|---|---|
| `current-fidelity` | `payloads/current-fidelity/` | None. Byte copy of `skills/dispel` at the baseline. |
| `scope-fidelity` | `payloads/scope-fidelity/` | The Fidelity section body becomes the candidate paragraph under the same heading. Self-check item 9 is deleted, because the candidate's last sentence carries that check. |
| `section-removed` | `payloads/section-removed/` | The Fidelity section and self-check item 9 are deleted. |

Each arm is a complete standalone skill: `SKILL.md` plus `references/archmage.md`, which the persona block loads. Every line outside the two selected blocks is identical across arms, including self-check items 1 to 8, the plain-speech source restrictions, the exempt-text rule and the authorization paragraph. The supporting file is byte-identical in all three.

`patches/scope-fidelity.patch` and `patches/section-removed.patch` are the exact unified diffs from the current entrypoint. `git apply` reproduces each arm from the current copy.

Verify the set, offline:

```bash
python3 -B evals/workflows/prose_ablation.py --check-payloads
```

The check re-derives both changed arms from the frozen current copy, recomputes every inventory and patch, and fails on any byte difference. A consistent re-hash of a wrong arm still fails, because the arm is rebuilt from the rule rather than trusted from its record. The report also says whether today's `skills/dispel` differs from the frozen current copy. That field is information; a later production edit does not change the frozen arms.

The set was built from a `git archive` of the baseline:

```bash
git archive 9d1aa521974bc7c72bf9cdd676de18c09a036468 skills/dispel | tar -x -C /absolute/scratch
python3 -B evals/workflows/prose_ablation.py --build-payloads /absolute/scratch/skills/dispel --out /absolute/new-set
```

The builder only reads its source and refuses a destination under `skills/`, `agents/` or `output-styles/`.

## Prose studies

A prose study manifest pins the payload set by path and by the SHA-256 of `payloads.json`. Each case carries its raw source files, an ordinary request and any protected spans. A protected span names a source file and text that must appear in that file verbatim.

```json
{
  "version": 1,
  "study": "prose-fidelity-confirmation-1",
  "host": "codex-cli 0.159.2",
  "model": "REPLACE_WITH_REQUESTED_MODEL",
  "reasoning": "medium",
  "seed": 20261017,
  "repetitions": 2,
  "payload_set": "/absolute/mana/evals/workflows/prose-ablation",
  "payload_set_sha256": "REPLACE_WITH_PAYLOADS_JSON_SHA256",
  "cases": [{
    "id": "REPLACE",
    "source_group": "REPLACE",
    "split": "confirmation",
    "request": "Rewrite notes.md as a short status update.",
    "sources": {"notes.md": "raw source text"},
    "protected_spans": [{"id": "config-sample", "file": "notes.md", "text": "exact substring"}],
    "timeout_seconds": 180
  }]
}
```

```bash
python3 -B evals/workflows/prose_ablation.py --freeze-study manifest.json --out /absolute/new-study
python3 -B /absolute/new-study/runner-source/prose_ablation.py --study /absolute/new-study --controls-sha256 SAVED_DIGEST --check
python3 -B /absolute/new-study/runner-source/prose_ablation.py --study /absolute/new-study --controls-sha256 SAVED_DIGEST --live --slot 1
```

Freeze copies the three arms, the patches, the raw sources and the runner, then prints an external `controls_sha256` pin. The schedule shuffles case, arm and repetition cells within each source group with the declared seed. Six groups, three arms and two repetitions allocate the 36 slots the decision names; the adapter caps a study at 72. Expected judgments never enter the manifest, the prompt or the response schema. Manifest validation rejects unknown fields, so an oracle label cannot ride along.

`shared_controls` in `controls.json` is one record for all arms: the prompt template, installed location, response schema digest, deterministic checks, disabled host features, read-only workspace, no delegation and no retries. Every arm installs its payload at `installed/payload/SKILL.md`, so the rendered prompt is byte-identical across arms for the same workspace path. Only the payload inventory differs.

## What each attempt keeps

Every attempt writes these files beside the evaluator-only controls, schedule and runner copy, outside the candidate workspace:

| File | Content |
|---|---|
| `raw-source/` | The frozen source bytes the candidate received. |
| `protected-spans.json` | Each span's text, file, offset and SHA-256. |
| `payload-source/` | The actual instruction bytes for that arm. |
| `prompt.txt`, `events.jsonl`, `stderr.txt`, `response.json` | The exact prompt and raw host records. |
| `final-output.md` | The `rewrite` field, written byte for byte. |
| `instruction-reads.json` | Exact complete payload retrievals, every command that names a payload file, and files with no observed read. |
| `evaluation.json` | Slot, arm, source group, split, request, source, span, payload and patch hashes, deterministic results, and empty human fidelity review fields. |

The attempt directory is also packed into `NNN.json.gz`, which `archive_delegated.py` verifies. Installed payload copies and Git internals stay out of the archive; `payload-source/` holds the instruction bytes.

Deterministic checks cover exact protected spans, unchanged source files, an unchanged workspace outside `artifacts/` and an unchanged HEAD. A lost span or an edited source is a task outcome and the next slot may run. An unvalidated host, a setup failure, a timeout, a malformed event record, a frozen-input change or an archive failure writes `results/STOP.json` and blocks later slots.

## Limits

These checks prove adapter and payload behavior. They are not a containment probe on a real host and say nothing about which arm is better. Source entailment, added claims and lost conditions still need the two blinded reviewers the decision requires; `fidelity_review` stays empty until they record judgments. A command naming a file shows intent to read it, not that its output reached the model, and hidden host context is not reconstructed.

```bash
python3 -B -m unittest discover -s evals/workflows -p test_prose_ablation.py
```
