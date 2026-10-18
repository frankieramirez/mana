# Refresh an installed control

Load during Refresh, when a project with an installed control has moved on: source renamed or deleted, configuration edited, tests changed, or a challenge has run. Refresh reads files, the ledger and retained evidence. It never executes project code, so it needs no execution authority. Applying its candidate edits project files and needs the same edit authority as installation.

```bash
bash "<SKILL_DIR>/scripts/generate.sh" refresh <repo> --out <candidate.json> [--challenge <evidence-dir>]
bash "<SKILL_DIR>/scripts/generate.sh" refresh <repo> --apply <candidate.json>
```

Keep the candidate outside the checkout and review its `edits` diffs and `findings` before applying. `--apply` recomputes the candidate from the current checkout and refuses when anything differs from what was reviewed, so a stale or edited candidate writes nothing.

## What it compares

The installation record in `docs/agents/readiness.md` is the base. It holds the generation head, each installed file's digest and blob id, and the marked discovery block. Each refresh record carries those forward with any applied changes. Without an installation record, refresh reports an ownership conflict and edits nothing.

| Observation | Result |
|---|---|
| Nothing material changed | No edit and no ledger record. A second refresh is byte for byte a no-op |
| A path in a feature record or the adapter configuration moved, and exactly one path holds identical content | `path-renamed`: a focused value edit to those records. Tests and runtime code are never edited |
| A path named by the package script behind `Command:` moved the same way | `command-path-renamed`: the script value changes |
| A path is gone, or several paths hold its content | `source-root-missing` or `path-missing` with candidates. No guess |
| Every source root of a feature is gone | `feature-implementation-missing`. The record, id and intent stay until a person decides |
| A mapped reach route is not a quoted literal in the feature's source roots | `route-missing`. A rename, a deletion and a route built at runtime look alike, so a person decides and the record stays |
| A scenario record has no literal registration, or a registration has no record | `binding-stale` or `binding-orphan`. Scenario ids are stable and never renamed |
| The break patch no longer applies | `break-renamed` when the proven renames fix its headers, otherwise `break-stale` |
| The configured bindings changed and the marked block is still the installed one | `managed-update`: only the bytes between the markers change |
| A person edited the marked block | `managed-section-edited`, kept. If the generated block changed too, `managed-conflict` |
| The runtime template changed | `runtime-update` when the runtime still equals its generated base or merges cleanly with it. Overlapping hand edits are a `runtime-conflict`. A base whose bytes are not in the repository is `runtime-base-missing`, and hand edits stay |
| The control `Command:` names a package script that is gone | `command-missing` |
| An instruction port cannot be matched to exactly one profile in `.claude/launch.json` using it | `port-drift`, with the attribution in its evidence. Neither file is edited |
| Installer staging or recovery files remain | `recovery-files`, with what each one matches |

Severity says what happens next. `proposed` findings carry an edit. `needs_adjudication` and `conflict` findings name what a person decides; refresh never chooses for them. `info` records kept human bytes. Any conflict withholds every edit, and applying then only records the conflict in the ledger.

Distinct launch profiles are facts to keep apart. A port that matches the profile its line names is consistent, even when another profile uses a different port. Refresh never selects a port by proximity and never unifies profiles.

## Intent

Refresh never writes `knowledge`, summaries or scenario expectations. Its edits touch recorded paths, the break patch headers, the marked block and the runtime only; the confirmed text stays where a person put it, with its history in version control. `feature-implementation-missing` names the feature's `knowledge` in its evidence. A passing challenge records execution evidence and leaves `proposed` intent proposed.

## Challenge evidence

`--challenge <dir>` reads a retained `challenge.sh` evidence directory. Refresh rechecks every file in its manifest and derives the outcome from the hashed `challenge.json`. The later `result.json` can only lower that outcome. The state is `verified` only when the evidence verifies, every probe passed, the challenged head and the current HEAD differ at most in the ledger file, and nothing outside the ledger is uncommitted. A failed or interrupted challenge is `failed`; an incomplete, stale or unverifiable one is `unverified`. Either way the record keeps the evidence path, manifest digest and run ids, the evidence directory is never touched, and the Control pointer stays as it was.

## Interrupted installation

Pass the installation map with `--map` when an install stopped before writing its ledger record. Refresh lists complete, absent and conflicting outputs, source drift since the map, and leftover staging or recovery files, and writes nothing. Its recovery work says what to decide, then to restore the original bytes of the complete outputs and rerun install with the same map. Recovery files are reported and kept.

## Limits

Manifest hashes show that a retained evidence copy is intact since the challenge wrote it; they do not show who produced it, so keep evidence where only the challenger writes. Route detection reads quoted path literals in the source roots and does not look for routes no feature reaches. Renames are proven only by identical content. A runtime merge needs the generated base blob in the repository. That holds for the installed runtime once the candidate is committed, and fails after a merged update, whose generated base was never committed. Unattended refresh and adoption of an existing control without a ledger remain separate work.
