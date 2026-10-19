# Prove what the review could not

Load at Stage 5c, after the validator's verdicts are applied and pass 2 has run again. Paths beginning with `references/` or `scripts/` are relative to the skill directory.

Reviewers and the validator read code. Some findings stay a claim after both: the defect is plausible, the cited line is real, and nobody ran anything. When such a finding would block the merge, one small run of the real code settles it faster than another reader.

## When to run

Pick at most two findings from the final pass 2 `merged.json`. A finding qualifies when all of these hold:

- It is a primary P0 or P1 in `findings`, or a residual risk you judged would be P0 or P1 if real.
- Its evidence is static: quoted lines, a traced path, an argument. Nothing in its evidence executed the code.
- The fact it turns on can be checked by calling the reviewed code in under two minutes, with the dependencies the repository already pins. No network, credentials, device, database server, or browser.

Skip the stage, and say so in one Coverage line, when no finding qualifies, when the request limited the review to reading code, when `python3` is missing, or when the code needs a dependency install that the request did not authorize. A skipped proof never lowers or raises a finding.

Run the proofs yourself, one after the other, in this context. They need the whole diff and the finding's evidence, and a subagent would only re-read both.

## How to run

Read `references/proof.md` in full before writing anything. It owns the snapshot, the source-origin check, the break, the coverage line, and the evidence to keep.

1. **State the fact.** Turn the finding into the fact it says is false, in one line a reader can check: "`lookup([])` returns None instead of raising" becomes the fact "`lookup([])` raises `KeyError`". The proof asserts the fact.
2. **Select the source.** Use `--revision` with the reviewed head under `pr-remote` or `branch-remote`, and `--working-tree` under `local-aligned` or standalone, so the proof runs the same bytes the reviewers read.
3. **Write the break.** A patch that makes the fact false the way the finding claims the code already does. If the finding is right, the reviewed code and the break fail the same way.
4. **Run it** with the bundled helper:

```bash
bash "<SKILL_DIR>/scripts/prove.sh" --repo "<repo root>" --revision "<reviewed head>" --proof "<run dir>/proof-<n>/fact.sh" --context "<run dir>/proof-<n>/context.json" --break "<run dir>/proof-<n>/break.patch"
```

Keep each proof's files under `$RUN_DIR/proof-<n>/`, where `<n>` is the finding's `#`. The helper prints its report and keeps its own run directory; record both paths.

## Read the outcome

| Report | What it means | What changes |
|---|---|---|
| `failed`, at the fact's assertion | The code breaks the fact. The finding is confirmed by execution. | Add a `confidence_assessment` at 100 whose `evidence` holds the report path and the failing assertion's output line. The finding's how-sure line says `confirmed by a run` with the report path. |
| `passed`, `challenge: detected` | The fact holds on the reviewed code, and the same proof caught the break. The finding is refuted. | Set `bucket: dismissed`, `stage: "proof"`, and a `reason` naming the fact and the report path. It appears under Dismissed, where the user can overrule it. |
| `passed`, `challenge: missed` or `not-run` | The proof never failed, so its pass proves nothing. | No change to the finding. |
| `unproven`, or `failed` before the fact's assertion | The run did not test the fact: missing dependency, wrong import, source-origin check, timeout. | No change to the finding. |

A refuted P0 or P1 still shows in Dismissed with its proof, because a wrong proof is cheaper to catch there than a wrong merge. A residual risk that a run confirms becomes a primary finding at the severity you judged, with the run as its evidence.

After applying outcomes, run pass 2 once more so numbering and counts stay final. Prune triage groups after drops.

## Coverage

One line per proof: `proof: #3 confirmed (<report path>, coverage: <coverage or examples>)`, `proof: #5 refuted (<report path>)`, or `proof: #2 unproven (<reason>)`. When the stage was skipped, one line: `proof: not run (<reason>)`. Under `mode:agent` the same outcomes go in `coverage.proofs` as `[{"finding": 3, "outcome": "confirmed | refuted | unproven", "report": "<path or null>", "coverage": "<text or null>", "reason": "<text or null>"}]`, and an empty array when the stage was skipped, with the reason in `coverage.notes`.
