---
name: setup-mana
description: "Set up a repository for the other skills: pick the issue tracker (GitHub, Linear, Jira, local files, or your own), map the triage labels, record the command that proves the project works, and write the docs/agents files the skills read. Run once per repo, and again to switch trackers. Use when asked to set up mana, configure the issue tracker, set up triage labels, or /setup-mana."
argument-hint: "[blank] [you-pick]"
disable-model-invocation: true
---

# Setup

Write the per-repo configuration the other skills read. Explore first, ask only what exploration left open, show the draft, then write. Re-running updates the same files in place.

## Operating principles

- **Explore before asking.** Every question you can answer from the checkout is not a question.
- **Recommended answer first.** Each section leads with the answer you would pick, so the user can accept it in a word. `you-pick` accepts every recommendation.
- **Never record a value you did not confirm.** A tracker the token cannot read, a label that does not exist, or a validation command that does not run stays out of the files. Say what is missing instead.
- **Secrets stay in the environment.** The files name the variable, never the value.
- **Edit the file that exists.** `CLAUDE.md` or `AGENTS.md`, whichever is already there. Never create the second one, and when one is a symlink to the other, edit once.

`SKILL_DIR` is the absolute directory this SKILL.md lives in. The Bash tool forgets variables between calls, so every block that runs the bundled script sets `SKILL_DIR` again on its first line.

## Execution spine

1. Explore (Stage 1).
2. Ask the open sections (Stage 2).
3. Draft, confirm, write (Stage 3).
4. Verify (Stage 4).

---

## Stage 1: Explore

Read, do not assume:

```bash
git remote -v
gh repo view --json url,defaultBranchRef --jq '{url, default: .defaultBranchRef.name}' 2>&1 | head -3
ls -l CLAUDE.md AGENTS.md CONTEXT.md CONTEXT-MAP.md 2>/dev/null
ls docs/agents docs/adr .scratch 2>/dev/null
gh auth status 2>&1 | head -5
gh --version | head -1
env | grep -o -E '^(LINEAR_API_KEY|LINEAR_TEAM|JIRA_BASE_URL|JIRA_EMAIL|JIRA_API_TOKEN|JIRA_PROJECT)=' | sort
[ -n "${ORCA_WORKTREE_ID:-}" ] && command -v orca >/dev/null && echo orca: yes
ls orca.yaml .worktreeinclude 2>/dev/null
```

Then:

- **Tracker signals.** A GitHub remote suggests GitHub. `LINEAR_API_KEY` set suggests Linear. `JIRA_BASE_URL` set suggests Jira. A populated `.scratch/` suggests local files. Existing `docs/agents/issue-tracker.md`: read its `Tracker:` line; that is the current choice.
- **Labels.** `gh label list --limit 200 --json name --jq '.[].name'` on GitHub. Look for names that already mean bug, enhancement, or a triage state (`kind/bug`, `status: blocked`, `triage`). Existing `docs/agents/triage-labels.md`: read it.
- **Validation command.** In this order, stop at the first hit: a `Validation:` line in an existing `## Agent skills` block; `package.json` scripts named `test`, `typecheck`, `lint`, `check`; `Makefile` or `justfile` targets with those names; `pyproject.toml`, `Cargo.toml`, `go.mod` defaults. Run the candidate once. It must exit 0 or fail on a test, never on "command not found".
- **Proof capture.** Whether the host offers a screenshot or recording tool, and whether `gh --version` is 2.99.0 or newer (needed for `--attach`). Inside an Orca worktree, `orca screenshot` is such a tool.
- **Orca.** `orca: yes` means the session runs inside an Orca worktree. Then `orca linear team list --json` succeeding is a Linear signal and counts as a connector. Note whether `orca.yaml` and `.worktreeinclude` exist, and whether the validation command needs installed dependencies or gitignored files (`.env`, `node_modules`) that a fresh worktree would not have.
- **Monorepo signals.** `pnpm-workspace.yaml`, a `workspaces` field, or `packages/*` with their own `src/`. Absent in almost every repo.
- **Pointer file.** Which of `CLAUDE.md` or `AGENTS.md` exists, whether one is a symlink to the other, and whether an `## Agent skills` block is already present.

Summarise what is present and what is missing in a few lines.

## Stage 2: Ask

Take the sections in order. One section, one answer, then the next. Skip a section exploration already settled and say so in one line. Under `you-pick`, show each recommendation and continue.

**A. Issue tracker.** Lead with the signal from Stage 1.

| Choice | Needs |
|--------|-------|
| GitHub | `gh` logged in with write access to the repo |
| Linear | A Linear connector the host exposes (`orca linear` inside an Orca worktree counts), or `LINEAR_API_KEY` in the environment. Plus the team key (the prefix on issue identifiers, like `ENG`) |
| Jira | A Jira connector the host exposes, or `JIRA_BASE_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN` in the environment. Plus the project key. Optional `JIRA_ISSUE_TYPE`, default `Task` |
| Local | nothing. Tickets are markdown files under `.scratch/` |
| Other | one paragraph from the user describing how to create, read, label, assign, and close a ticket |

A connector covers this session. The environment variables cover a scheduled agent, another host, or CI, where no connector exists. When only the connector is present, say so: the loop works here, and an unattended run will need the variables set where it runs. A required variable that is not set and no connector either: tell the user the variable name and where to get the value, and do not continue to Stage 4 for that tracker. Do not ask for the value itself.

**B. Triage labels.** Ask one question: keep the default names? The defaults are `bug`, `enhancement`, `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`, each string equal to its role. Only on no, or when Stage 1 found labels that already mean the same thing, collect the mapping. Jira has no label registry, so any string works there. Skip this section for `local` and `other`; the role names are the strings.

**C. Proof.** Confirm the validation command from Stage 1, or ask for one when nothing ran. Then how proof gets captured for pull requests: a screenshot or recording tool the host offers, or command output rendered to an image. Record both.

**D. Domain docs.** Single-context is the default: `CONTEXT.md` at the root and ADRs in `docs/adr/`. Write it without asking. Offer multi-context (`CONTEXT-MAP.md` pointing at per-area files) only when Stage 1 found monorepo signals.

**E. Worktree files.** Only when Stage 1 found Orca. Every Orca worktree is a fresh checkout without gitignored files, so a validation command that needs `.env` or `node_modules` fails there until someone sets them up. Recommend two files Orca reads, and skip the section when the command needs neither:

- `.worktreeinclude` at the repo root: one gitignored file or directory per line to copy into each new worktree (`.env`, `.env.local`). Small files only; a copied `node_modules` stalls creation.
- `orca.yaml` at the repo root: `scripts.setup` holding the install command, and `worktree.sharedDirectories` listing large rebuildable gitignored directories (`node_modules`, `.cache`) that exist in the primary checkout, so they are shared rather than rebuilt.

An existing file is shown and left alone unless the user wants it changed.

## Stage 3: Draft, confirm, write

Load the template for the chosen tracker and `references/triage-labels.md`. Fill them from the answers. Show the user the three drafts together:

1. `docs/agents/issue-tracker.md`
2. `docs/agents/triage-labels.md` (GitHub, Linear, Jira only)
3. The `## Agent skills` block for `CLAUDE.md` or `AGENTS.md`
4. `.worktreeinclude` and `orca.yaml`, when section E applied

Let them edit. Then write. An existing `## Agent skills` block is replaced in place; the rest of the file is untouched. When neither pointer file exists, ask which one to create.

The block:

```markdown
## Agent skills

Issue tracker: <GitHub owner/repo | Linear team KEY | Jira project KEY | local files under .scratch/ | other>. See `docs/agents/issue-tracker.md`.
Triage labels: <defaults | mapped>. See `docs/agents/triage-labels.md`.
Validation: `<the command>`
Proof: <screenshots and recordings via the host's browser tool | Orca's embedded browser | command output as an image>
Domain docs: <single-context: CONTEXT.md and docs/adr/ | multi-context: CONTEXT-MAP.md>
```

Other skills read the `Validation:` line before guessing a test command, and the tracker file before touching a ticket.

For `other`, write `docs/agents/issue-tracker.md` from `references/issue-tracker-other.md` with the user's paragraph under Conventions. There is no adapter; the skills follow the prose.

## Stage 4: Verify

Nothing is done until the tracker answers. With a connector, read the team or project through it and list its labels. Without one:

```bash
SKILL_DIR="<absolute path of the directory containing this SKILL.md>";
bash "$SKILL_DIR/scripts/tickets.sh" <adapter flags from the tracker file> check
```

Exit 3 means the token was refused: say which variable or login to fix, and stop. Then create the missing labels, through the connector or the script:

```bash
SKILL_DIR="<absolute path of the directory containing this SKILL.md>";
bash "$SKILL_DIR/scripts/tickets.sh" <adapter flags> ensure-labels --color d73a4a <category strings>
bash "$SKILL_DIR/scripts/tickets.sh" <adapter flags> ensure-labels --color 0e8a16 <state strings>
```

Skip both for `local` and `other`. When the variables are set as well as the connector, run `check` through the script too, so the unattended path is known to work before a routine depends on it. Run the validation command once more if Stage 1 did not.

## Report

```
Setup
Tracker: <choice and project>
Check: <user, project | refused: what to fix>
Labels: <created: list | all present | none: local>
Validation: <command, and its result>
Wrote: <files written | updated in place>
```

Say that the files apply to new sessions, that editing them by hand is fine, and that re-running this skill is only needed to switch trackers.

## References

| Reference | Load at | Purpose |
|-----------|---------|---------|
| `references/issue-tracker-github.md` | Stage 3, GitHub | Tracker file template |
| `references/issue-tracker-linear.md` | Stage 3, Linear | Tracker file template |
| `references/issue-tracker-jira.md` | Stage 3, Jira | Tracker file template |
| `references/issue-tracker-local.md` | Stage 3, local | Tracker file template |
| `references/issue-tracker-other.md` | Stage 3, other | Tracker file template |
| `references/triage-labels.md` | Stage 3 | Label mapping template |

## Scripts

`scripts/tickets.sh` talks to the tracker: `check`, `ensure-labels`, and the operations the other skills use. GitHub needs `git` and `gh`. Linear and Jira need `python3` and the environment variables above. `tickets.sh -h` prints usage.
