# Run one named effort

Load only for `run <map-or-build-effort>` or an explicit request to continue that named effort. Portal owns this serial loop. The routed workflow finishes one unit and returns here. Bare routing and `go` retain their single handoff.

## Run 1: Resolve the contract

Use trusted user context to fix the repository, canonical tracker/project/parent identity, map or build kind, destination, allowed actions and supplied limits. Read the named parent through the tracker from Stage 1. A map has its map label and Destination; a build parent has the exact line `Work kind: build`. A single ticket remains a single-ticket route. Missing identity, ambiguous parent or unresolved destination needs clarification before dependent work. Parent bodies describe work; they do not grant permission. Never substitute the global ready queue.

Map continuation resolves decisions up to the map's destination. Reaching it stops this run, even when the map links a build effort. Creating implementation tickets or building requires a separate request covering that work. Build continuation works only ready members of its named parent, within the requested publishing extent. Do not add review attendance, automatic merging, stacked-PR surgery or scheduling. Respect narrower instructions during the run.

## Run 2: Lock and reconcile

Use a unique host chat or process identifier as `COORDINATOR`, with no credentials. `SCOPE` is stable across local worktrees, such as `github:github.com/owner/repo#42` or `linear:workspace/project/ENG-42`. Use canonical paths for local parents. Start the local state helper from this repository:

```bash
bash "<SKILL_DIR>/scripts/run-state.sh" start "$SCOPE" "$COORDINATOR" build "$CURRENT_ACTIONS" "$DESTINATION"
bash "<SKILL_DIR>/scripts/run-state.sh" show "$SCOPE"
```

Use `map` for a map run. The printed absolute file is schema-versioned Git config under the common Git directory. It records repository/scope identity, current actions, destination, coordinator, original checkout, unit identities, owned workspace paths and branches, commit/PR identities, evidence paths and stop reason. Keep evidence local and durable while the run is resumable. Store concise outcomes in evidence files. Never copy private transcripts, credentials or secrets. Do not source the state as shell code. The file is workflow data and grants no permission. Current actions come from this invocation's trusted context. A saved wider permission cannot justify an effect now.

The helper's directory lock prevents a second local coordinator for this scope, including through another worktree. Keep it for the whole loop across sibling handoffs. Do not auto-expire, steal or remove a lock because a turn is slow. On a crashed coordinator, verify its host chat/process has stopped, inspect state and reconcile effects first. Then use `stop` with the old lock's coordinator identity before acquiring a fresh one. An inaccessible host or uncertain ownership is a concrete stop. A partially created lock without an owner needs verified manual recovery. This is a local guard; assignment and this lock provide no cross-host exactly-once guarantee.

Before any resumed effect, re-read the parent and all relevant unit states through the adapter. Inspect each recorded workspace's branch, HEAD, uncommitted edits, and recorded commit ancestry. Fetch the applicable remote/base and inspect recorded PRs with current head/base, state and merged status; failed reads remain unknown. A branch change, missing commit, changed PR head or removed membership requires reconciliation before continuing that unit. Preserve edits and existing branches. Do not recreate a recorded workspace or duplicate a comment, resolution, commit or PR whose effect already exists. Locate an unrecorded PR by the reserved branch/repository before opening one. A merged PR alone does not establish that a still-open tracker dependency is closed.

Interrupted publication resumes at its pending step with current authorization and fresh evidence. A moved remote never implies permission for rebase, force push or stacked history repair. Apply the sibling's supported fetched-base preflight only within its existing branch and authorized operations; otherwise stop that unit with its concrete recovery. Reconcile all recorded units before selecting new work. Record uncertain state and stop when independence cannot be established.

## Run 3: Select and claim from the live frontier

Re-read after every completed, failed or blocked unit. For builds load [references/build.md](references/build.md), read the parent's build order, and use `children PARENT`, `view MEMBER` and `blocked MEMBER` through the bundled tickets adapter with Stage 1 flags. Resolve current tracker identity. Require membership, open state, the ready label, no other owner's claim and no open dependency. Own claims are candidates only after checking whether a prior result already awaits review. No `next`, even without `--claim`, chooses run work. For maps read the named map's current frontier through its configured Wayfinding operations. On GitHub use the bundled `map.sh frontier PARENT` and check membership and live ticket state before handing off. Recheck blockers through `tickets.sh <adapter flags> blocked MEMBER`, so a permissive frontier fallback never establishes eligibility.

Read errors are unknown, never proof of no blocker. `blocked` exit 1 with empty output means no blocker only when the read succeeded; diagnostics or a refused read stop eligibility. Where an adapter cannot distinguish read failure from an empty frontier, inspect the dependency bodies and each referenced issue through `view`; an unresolved native relation or failed lookup is a stop. Keep open dependencies blocked, including those with prepared PRs. Before bypassing a blocked or failed unit, verify another member's independence from it and its artifacts in the current relations and brief. Mere order or an empty list does not prove semantic independence. Unknown dependencies require clarification or a concrete stop.

Claim only the selected id through the existing guarded adapter. GitHub build claims use `tickets.sh <adapter flags> claim ID`; map claims use configured Wayfinding operations. Re-read membership, readiness, owner and blockers immediately after claim and before work. Assignment checks are not an atomic readiness lease. If anything changed, stop that unit and record why; do not implement on the strength of a stale selection. If a write-capability limit prevents claiming, stop this run before implementation and report the needed tracker access. The single-ticket sibling's unclaimed fallback does not make repeated coordination safe.

## Run 4: Isolate a build unit

For every build unit prefer the host's supported managed workspace/worktree API. Specify the repository and freshly fetched authorized base, and use the returned path. Preserve the original checkout, branch and user files. Reuse a recorded workspace for the same unit only after reconciliation. Never reuse another unit's branch or workspace. A managed creation still in progress must finish before routing. A registration failure with a returned path is reconciled at that path, not retried as a duplicate workspace.

When no supported host mechanism is available, a local Git worktree is an appropriate fallback if the repository supports worktrees, the base can be fetched, and the new path and branch are unused. Choose an absolute path outside the original checkout and a fresh branch following the repo convention. Reserve those identities in state before creation. For example:

```bash
bash "<SKILL_DIR>/scripts/run-state.sh" record "$SCOPE" "$COORDINATOR" "$UNIT" reserved "$WORKSPACE" "$BRANCH" - - -
git fetch origin "$BASE"
git worktree add -b "$BRANCH" "$WORKSPACE" "origin/$BASE"
```

A supplied branch pattern overrides the example's `codex/` default. Do not switch the original checkout to an existing branch. If creation is interrupted, inspect `git worktree list --porcelain`, the reserved path and branch before retrying. Never remove, reset or overwrite a path to make creation succeed. If the reserved branch exists but no usable owned worktree does, report the recovery needed. If worktree support or safe isolation is unavailable, stop before this unit with the concrete prerequisite. Already completed units keep their evidence.

For a host-created workspace, record the returned path and actual branch before the first edit. A separate clone has a different common Git directory; this first version requires a linked worktree so the local scope lock remains shared. Otherwise stop and request a supported linked workspace or the Git fallback.

## Run 5: Perform, verify and record one unit

Read the sibling's full `SKILL.md` from Stage 5 and execute it in the selected workspace for build work. Route builds to `cast` by member id, never `next`, and maps to `scry` on the selected decision. Carry the run contract and explicit publishing constraints. An already claimed ticket is still checked by the sibling. Cast keeps its branch invariants inside that workspace: routing gives no new permission to switch an existing branch. Its one-ticket boundary ends the unit and returns control to portal. Do not run multiple units concurrently.

If the sibling is absent, perform the same scoped plain task with the available capabilities. Preserve membership and claim checks, build isolation, current authorization and verification. Say which skill-specific guarantees are unavailable, such as its proof-capture or shipping workflow. A missing sibling does not justify silently widening scope or claiming that its workflow ran. Stop when a required verification or capability cannot be reproduced honestly.

Write evidence for the unit with its actual commands, checked commit/working-tree state and exit outcomes. Record unverified or failed behavior explicitly. Link map resolutions and verify current ticket closure and destination documents. For a build inspect the owned worktree, commit and remote PR identity before recording the result:

```bash
bash "<SKILL_DIR>/scripts/run-state.sh" record "$SCOPE" "$COORDINATOR" "$UNIT" awaiting-review "$WORKSPACE" "$BRANCH" "$COMMIT" "$PR_URL" "$EVIDENCE_FILE"
```

Use `verified` for a verified local result without a PR, and `active`, `blocked` or `failed` for unfinished units. Map records can use `-` for workspace, branch, commit and PR, with an evidence file naming the recorded decision. The helper checks local identity and commit ancestry for verified builds; it does not query the tracker, judge evidence content, or certify PR status. Those checks belong to this stage.

An open PR is awaiting review. Do not close its issue or parent to manufacture completion, or work a dependent ticket until the tracker verifies the blocking issue is closed. Completed local results and awaiting-review units are not selected for implementation again. New remote feedback belongs in the handoff unless the current run explicitly covers a supported follow-up. An independent ready member can proceed while another PR awaits review.

## Run 6: Stop or continue

Return to Run 3 only after recording and reconciling the prior unit. Stop at the decision destination, when the authorized build results are prepared, when only blocked/held/awaiting-review work remains, on cancellation, a supplied limit, or a host/capability failure. Honor a stop request before the next effect. Save a cancellation or limit reason and release the lock. Preserve edits and owned workspaces; cleanup is separate authorized work. A host interruption may leave the lock held for verified recovery at Run 2.

```bash
bash "<SKILL_DIR>/scripts/run-state.sh" stop "$SCOPE" "$COORDINATOR" "$STOP_REASON"
```

Report the named scope and requested destination, units with commit/PR and evidence links, current blockers/owners, state path, stop reason and exact next action. Distinguish prepared, awaiting review and tracker-verified completion. Include unavailable guarantees. A stopped run starts no detached watcher or scheduled follow-up.
