# Dispatch and collection

Load at Stage 3d after selecting the roster, continuing through Stage 4. Paths beginning with `references/` are relative to the skill directory.

### Stage 3d: Create the run directory

```bash
SCRATCH_ROOT="/tmp/scan-$(id -u)";
if [ -L "$SCRATCH_ROOT" ]; then echo "unsafe scratch root symlink: $SCRATCH_ROOT" >&2; exit 1; fi;
install -d -m 700 "$SCRATCH_ROOT" || exit 1;
if [ -L "$SCRATCH_ROOT" ] || [ ! -O "$SCRATCH_ROOT" ]; then echo "scratch root not owned by current user" >&2; exit 1; fi;
chmod 700 "$SCRATCH_ROOT" || exit 1;
RUN_ID=$(date +%Y%m%d-%H%M%S)-$(head -c4 /dev/urandom | od -An -tx1 | tr -d ' ');
RUN_DIR="$SCRATCH_ROOT/$RUN_ID";
(umask 077; mkdir -p "$RUN_DIR/returns") || exit 1;
echo "$RUN_DIR"
```

**Save the harvest.** When Stage 2b ran, write its payload now to `$RUN_DIR/harvest.json` as `{"fetched_at": "<ISO 8601 UTC>", "payload": <the raw GraphQL response>}`.

**Check for a prior run of the same diff.** Compute the current patch-id (`git diff "$BASE" | git patch-id --stable | cut -d' ' -f1`, the same working-tree diff Stage 1 computed, or the two fetched refs under `pr-remote`) and look through `$SCRATCH_ROOT/*/metadata.json` for a run with the same `pr` (or the same `branch` when standalone). A matching `patch_id` means that report reviewed this exact diff: say so in one line with its `report.md` path, then continue. Never skip the review on that basis.

**Announce the team** before spawning: name the always-on reviewers plainly, spec plus job, and give each conditional one a one-line reason it was added (the real concern, not the keyword that matched). Name the peer by its CLI when one is requested. This is progress reporting, not a confirmation prompt.

## Stage 4: Dispatch and collect

### Inline fast pass

Immediately before the first dispatch, scan the diff you already hold for high-signal obvious problems: injection or data-safety, broken control flow, a missing `await`, a swapped argument or off-by-one, an enum or status added without updating its sibling switch, a null deref the diff makes reachable. No deep analysis, no reading beyond the diff except a quick grep for enum completeness. Quote the verbatim motivating line, same bar as a persona finding.

Show it only when it finds a P0 or P1 candidate, under a clearly preliminary header, with one line saying the items are unverified and will be deduplicated into the final report. Otherwise emit one progress line and move on. Do not assign stable `#` numbers here.

Write the result as an artifact, `$RUN_DIR/fast-pass.json`, in the schema shape with `reviewer` set to `fast-pass` (an empty `findings` array when nothing was found). The fast pass enters synthesis as pseudo-reviewer `fast-pass` with a hard cap because it shares your context and blind spots: **every `fast-pass` finding is clamped to confidence 50**. The merge script enforces the cap. No reviewer count raises confidence; only inspected evidence can justify a stronger anchor during reconciliation. Never seed its candidates into persona or validator prompts; that manufactures the false agreement the cap exists to prevent. Under `mode:agent`, run the scan internally but emit no preliminary block.

Reconcile it in the final report: a preliminary item that did not survive gets a one-line "Preliminary fast-pass items withdrawn: n (reason)" note, so a user who saw a scary preliminary finding learns it was cleared.

### Model tiering

`protection-warrior`, `subtlety-rogue`, and `havoc-demon-hunter` inherit the session model with no override; they do the highest-stakes analysis. For every other reviewer, use a supported mid-tier model exposed by the host, while preserving explicit user or repository model routing. Resolve the model from the host's available choices; never invent an identifier or assume that every host has the same tiers. Apply an override only when the host supports it and the active routing permits it. If no suitable mid-tier choice is available, omit the override and inherit the session model. Record the effective routing when the host reports it, but do not print tiers to the user.

### Cross-model peer, only when requested

When `peer:<cli>` was passed, or the `## Agent skills` block in `CLAUDE.md` or `AGENTS.md` has a `Peer reviewer:` line, read `references/peer-review.md` and preflight the route before staging anything:

```bash
bash "<SKILL_DIR>/scripts/review.sh" peer --check --cli <cli> --run-dir "$RUN_DIR" --host <anthropic|openai|google|xai|unknown> [--named-by-user]
```

`--named-by-user` is set only when the token named the CLI. Exit 0 prints the disclosure line; repeat it to the user verbatim, then drop the local `havoc-demon-hunter` from the batch and run the peer in its place. Exit 2 means the peer cannot start (missing CLI, same family as the host without the token); keep the local `havoc-demon-hunter` and record the reason for Coverage. When a peer was never requested, none of this runs and nothing is printed about it.

### Staging and spawning

Write `full.diff` and `files.txt` into `$RUN_DIR` and pass those **paths** instead of inline content when the diff is large; inline a small one. Pass `{run_id}` and `{run_dir}` to every persona so it can write `{run_dir}/{reviewer_name}.json`. For a peer, also write `peer-constraints.md` and `peer-brief.md` as `references/peer-review.md` describes.

Before assembling any prompt, read these from this skill's directory, in one parallel wave along with the selected persona files: `references/subagent-template.md`, `references/diff-scope.md`, `references/findings-schema.json`.

Spawn each selected reviewer as a **generic subagent** seeded with its persona file. Do not use typed agent names. Omit the `mode` parameter so the user's permission settings apply. Launch reviewers up to the host's active-agent capacity; read-only reviewers can inspect the same files. A blocking spawn returns its result directly. An asynchronous spawn returns an ID: retain it and use the host's supported wait or completion mechanism to collect its result. Individual asynchronous spawn calls can run concurrently without a batch tool. When a peer passed preflight, launch its read-only command and track its completion alongside the reviewers:

```bash
bash "<SKILL_DIR>/scripts/review.sh" peer --cli <cli> --run-dir "$RUN_DIR" --brief "$RUN_DIR/peer-brief.md" --constraints "$RUN_DIR/peer-constraints.md" --host <family> --timeout 540 [--named-by-user]
```

Set the Bash tool's own timeout on that call to its maximum (600000 ms in Claude Code) so the harness never kills the shell before the script's `--timeout` fires; a killed shell leaves no output file and no exit code to act on.

Refill as slots free until the roster is exhausted; never hard-code a batch size. On a concurrency-limit error, keep the unlaunched reviewer queued and retry after a running reviewer completes. If the host offers only serial blocking calls, run the roster sequentially. Never fabricate task IDs or force an unsupported model or dispatch parameter.

Prefer completion events or bounded waits over repeated status reads. Use a status read when needed to recover a task's state; avoid busy polling and unchanged status updates. Collect **every** spawned reviewer before synthesis; synthesis on a partial roster is a defect. A peer that exits 2 or 3 after preflight passed (could not start after all, or started and returned nothing usable) gets one more dispatch of the local `havoc-demon-hunter` when capacity permits, and Coverage says `peer: not started (<reason>)` or `peer: no usable output (<reason>)`.

After collection, for any reviewer whose artifact file is missing or fails to parse, write its compact return to `$RUN_DIR/returns/<reviewer_name>.json` so the merge can still use it. A reviewer that returned nothing usable is a failed reviewer: name it in Coverage, never invent its findings.

Each persona subagent receives: its persona content, the shared diff-scope rules, the JSON schema, PR metadata in a `<pr-context>` block when reviewing a PR, the `<requirements>` block from Stage 2c, the intent summary, the file list and diff (or staged paths), the scope mode and remote head ref when set, and its run ID and reviewer name. Plus, for specific reviewers: `<standards-paths>` for `retribution-paladin`, `<review-base>` for `unholy-death-knight`, and the harvested feedback from Stage 2b for `lore-bard`.

Persona subagents are **read-only** toward the project: non-mutating inspection only, including read-oriented `git` and `gh` (`git diff`, `git show`, `git blame`, `git log`, `gh pr view`). The one permitted write is their own artifact file. They never edit project files, switch branches, commit, push, or post anything.
