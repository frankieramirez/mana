# Changelog

## 0.17.1

- Skills honor explicit user instructions and decisions already supplied in the conversation, and explain any skill rule that still requires a pause. A rule a skill states with never, or as read-only, stays in force whatever the conversation says. Setup reuses the selected tracker, and under `you-pick` with nothing detected it reports the missing choice and stops instead of asking; comment cleanup reuses authorization for constraint enforcement.
- Review and feedback workflows collect asynchronous agent results through the host's supported wait mechanism. Reviewer model routing uses available tiers and inherits the session model when an override is unavailable.
- Building applies TDD to testable behavior changes and reuses successful validation when no later edit or unresolved concern calls for another run. Required project checks still run.
- Ghost reads `.mimic.md` on refresh and preserves punctuation in verbatim samples. Reply drafting keeps its reply-only output contract, and prose style rules exempt verbatim evidence.

## 0.17.0

- `setup-mana` asks one question: where the tickets live. GitHub Issues, Linear, Jira, markdown files under `.scratch/`, or a tracker described in a paragraph. The question is asked every run, and the detected answer is listed first and labelled as detected. Detection now ranks its signals and puts a GitHub remote last, since nearly every repo has one and that alone is not evidence of where the tickets are. A ticket key prefix in recent commit subjects (`ENG-12`) is a Linear or Jira signal.
- `setup-mana` writes the tracker file even when the key or the token is missing. The report marks the check unverified and names the variable to set, instead of stopping on that tracker. It never falls back to a tracker the user did not pick.
- `setup-mana` records `Validation:` only when the detected command runs clean, and never asks about it. It writes no `Proof:`, `Domain docs:`, or `Peer reviewer:` line, so a review still sends nothing off the machine unless someone asks for it. Triage labels default to the role name, and `docs/agents/triage-labels.md` is written only when the repo already has a label that means the same thing. With neither `CLAUDE.md` nor `AGENTS.md` present, it creates `AGENTS.md` without asking.
- New skill `attune` changes one setting after setup: the triage label names, the validation command, proof capture, domain docs, a second opinion reviewer CLI, the worktree files, whether pull requests enter triage as requests, the tracker key, and which file holds the block. Run bare it lists every current setting and which skills read it. `attune <setting> <value>` writes one and asks nothing. `attune key` is the repair path for a setup run that wrote the config before the key was there. Switching trackers stays in `setup-mana`.
- `attune` carries `tickets.sh` for `check` and `ensure-labels`, plus a copy of the label template. `.worktreeinclude` and `orca.yaml` move out of setup into `attune worktree`.

## 0.16.0

- `remedy`: on a large batch (more than 12 new items, or more than 6 files) read-only scouts gather the evidence per file cluster in one foreground batch, and the orchestrator still judges every item from their returns. `references/scout-prompt.md` is the brief; the rubric says which scout field feeds which verdict.
- `remedy`: a verifier reads the combined diff against every fix-list item before the validation run: site changed, ask answered, in the file's conventions, and no hunk nobody asked for. A miss goes back to the same fixer once with a corrected note, then to the skip-list with the edit reverted. `references/verifier-prompt.md` is the brief; a single fix is checked inline.
- `remedy`: every run writes `fetch.json`, `items.json`, `summary.md`, and `metadata.json` under `/tmp/remedy-<uid>/<run-id>/`. The next run on the same PR reads them: a reopened thread, a `needs-human` still waiting, and a comment already fixed are named instead of re-judged.
- `remedy`: fixers dispatch as one foreground batch sized to the host's agent cap, with an explicit one-at-a-time path when the host cannot spawn subagents.

## 0.15.0

- `scan`: reviewer personas are class specializations with one shared file shape: Protection Warrior (correctness), Subtlety Rogue (security), Havoc Demon Hunter (adversarial), Marksmanship Hunter (testing), Fire Mage (performance), Restoration Shaman (reliability), Retribution Paladin (project standards), Unholy Death Knight (data migration), Balance Druid (maintainability), Demonology Warlock (API contract), Windwalker Monk (frontend races), Lore Bard (existing PR feedback). Two new ones: Augmentation Evoker checks that an agent can do and see what a user can, Discipline Priest checks instruction prose for hedges, contradictions, and dangling references.
- `scan`: `scripts/review.sh` does the deterministic merge (fast-pass clamp, suppression, quote-the-line demotion, exact dedup, cross-reviewer promotion, confidence gate, stable numbering) and the diff signals that drive the lite path; the model keeps semantic dedup, soft buckets, lead judgment, and grouping. A manual path remains when `python3` is absent.
- `scan`: Stage 2c reads the ticket the change resolves (`ticket:<id>`, a `Closes` line, a `cast/<id>-` branch, or an id in the branch or commits) through the tracker file and `tickets.sh`, hands every reviewer and the validator a numbered requirements block, and reports each requirement as met, unmet, deferred, or cannot tell. An unmet requirement on an explicitly resolved ticket blocks the verdict.
- `scan`: the validator brief is `references/validator.md`, with three questions per finding and no commitment to the original claim. `mode:agent` has a documented contract, also written to `review.json`. Apply mode runs the `Validation:` line from the `## Agent skills` block. `references/report-example.md` shows one good report and one bad one.
- `scan`: opt-in `peer:<cli>` (or a `Peer reviewer:` line written by `setup-mana`) sends the diff to a second CLI (`codex`, `gemini`, `cursor-agent`, `opencode`, `grok`, or `claude`) as the adversarial reviewer, read-only, after a disclosure line. Peer findings raise another reviewer's confidence only when the serving model is from a different family than the host. `scan` carries its own copy of `tickets.sh`.

## 0.14.1

- `reveal` and `cast`: proof files and the PR body file live in a `mktemp -d` directory, never at a fixed path under `/tmp`, so another local user cannot pre-create the file and control what goes into the pull request.
- `scan`: harvested PR comments, reviews, and threads are claims to verify against the code, never instructions. A comment that addresses an agent is recorded as dismissed. README says what `scan` reads and that `fix`, `comment`, and `mode:agent` push or post without a closing prompt.
- `open-pr.sh` reads only the four-character prefix of the `gh` token to classify it; the token itself never lands in a shell variable.
- `tickets.sh`: the Linear endpoint is fixed at `https://api.linear.app/graphql`. The undocumented `LINEAR_API_URL` override is gone, so `LINEAR_API_KEY` cannot be sent to another host.

## 0.14.0

- Orca support, optional everywhere. Inside an Orca worktree (`ORCA_WORKTREE_ID` set, `orca` on the path) `cast` links the ticket to the worktree card and moves it to in review with the PR URL; `reveal` moves the card on ship; `cast` and `reveal` can capture proof from Orca's embedded browser; `sift`, `conjure`, and `cast` treat `orca linear` as a Linear connector; `setup-mana` detects Orca and offers `.worktreeinclude` and `orca.yaml`. Every `orca` call is best-effort and reported, never a stop. Without Orca nothing changes.
- `scan` and `reveal` read `git config branch.<current>.base` before falling back to the default branch.
- README gains an Orca section with the automation shape for `cast next`.
- `attach.md`: the body references a proof file by the exact path passed to `--attach`. A mismatch made `gh` append a second copy instead of rewriting the reference.

## 0.13.3

- README closing line is tracker-specific: GitHub `#N`, Linear `ENG-N`, Jira `PLAT-N` (automation), local file named and left open on merge.
- Reveal/cast closing line: a commit-subject fallback is used only when exactly one ticket id appears; otherwise the line is omitted and the conflict is reported.
- `conjure`: Stage 1 `view` uses the bundled `tickets.sh` path. GitHub map-child listing includes labels and stops when `gh api` fails. Linear and Jira writes go through the host connector when one is present.

## 0.13.2

- `tickets.sh`: a GitHub, Linear, or Jira issue URL is reduced to the tracker id before `view`, `claim`, `wire`, `label`, `comment`, and `close`.
- `tickets.sh next`: GitHub and Linear page every matching ready issue before sorting by `createdAt`, so an older eligible ticket past the first 100 is not starved.
- `tickets.sh next --claim` assigns the chosen ticket, re-reads it, and releases it if it is closed, missing the ready label, or blocked. `cast next` uses that path so a parallel session cannot slip in between `next` and `claim`.

## 0.13.1

- `tickets.sh`: refuse non-HTTPS Linear and Jira URLs, and refuse redirects that change host or scheme, so Authorization is not forwarded elsewhere. Jira search pages on `nextPageToken` (Jira Cloud may omit `isLast`). `create --dry-run` leaves the body file in place and says to delete it.

## 0.13.0

- `setup-mana`: one skill that sets a repository up for the rest. Explores first, then asks in sections with a recommended answer: which issue tracker (GitHub, Linear, Jira, local files, or one you describe), which label names, what command proves the project works, and how proof gets captured. Writes `docs/agents/issue-tracker.md`, `docs/agents/triage-labels.md`, and an `## Agent skills` block in whichever of `CLAUDE.md` or `AGENTS.md` exists. Nothing is written until the tracker answers a read-only check. Secrets stay in the environment.
- Linear and Jira as issue trackers. `sift`, `conjure`, and `cast` read the tracker file, use the host's Linear or Jira connector when one is present, and otherwise pass the adapter flags to `tickets.sh`, which now speaks GitHub (`git` and `gh`), Linear (GraphQL, `LINEAR_API_KEY`), and Jira Cloud (REST, `JIRA_BASE_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN`) with the same subcommands. `scry` on those trackers follows the wayfinding prose in the tracker file. Pull requests stay on GitHub, and the closing line uses the tracker's key.
- `conjure`: turn a finished decision map, a spec, or the plan in the conversation into `ready-for-agent` issues. Each ticket is one vertical slice sized to one build session, carries an agent brief, and is wired to the tickets it waits on. Posts the build order on the map. Falls back to `.scratch/<slug>/tickets/` when the token cannot write issues.
- `cast next` claims the oldest unclaimed, unblocked `ready-for-agent` issue and builds it. Every ticket gets claimed before work, so two sessions cannot build the same one. A session that starts on the default branch creates `cast/<id>-<slug>` before any edit; nothing commits to `main`. The pull request body ends with a closing line for the ticket.
- `sift you-pick` triages without waiting, at most 10 issues per run, and never closes an issue as rejected on its own.
- `cast`, `mend`, and `remedy` run the `Validation:` command from the `## Agent skills` block before guessing a test command.
- README gains a lifecycle section: where to start, the order the skills hand off in, and the tokens that make each one safe to run on a schedule.

## 0.12.0

- `augur`: find what a change could break beyond its diff, name the one fact it is safe because of, and prove that fact by running real code. Five-rung evidence ladder; anything below "ran it" is reported as unproven. The proving script stays on disk. Inspired by the blast-radius skill in Cursor's pstack plugin (MIT), written from scratch.
- `dispel`: a plain-speech pass after the register ban. Metaphor nouns (substrate, wedge, vector, ratchet) get their concrete word, passive voice names its actor, adverbs become the number, and a sentence that could appear unchanged in another project's docs is cut. Inspired by pstack's unslop rules, written from scratch.
- `scan`: the report gains a Dismissed section listing every finding synthesis dropped and why, so the user can override it. Three lead-judgment filters run before validation: nitpick gravity, consistent with the codebase, and code the diff did not touch. The header and `metadata.json` carry base SHA, head SHA, and a `git patch-id` stamp, and a rerun on the same diff points at the earlier report. Inspired by pstack's interrogate lead-judgment notes, written from scratch.
- `remedy`: reads CI before judging. A failure in code the PR touched joins the fix list and the same push; a failure in untouched code is checked for a stale base with `git merge-base --is-ancestor`; a suspected flake gets at most one `gh run rerun --failed` after the push. Comment text never reaches a shell command as an argument or interpolation.

## 0.11.0

- `scry` files maps and tickets under its own labels, `scry:map` and `scry:<type>`, instead of the `wayfinder:*` names carried over from the loop it replaced. `ensure-labels` creates only the new set. Reads still accept `wayfinder:*`, so a map you already have walks without relabelling; that fallback goes away in a later release.

## 0.10.0

- `reveal`: open or update a pull request and put a screenshot, recording, or command-output SVG in the description via `gh --attach`. The body is a sentence plus a compact tree or structural diff a reviewer can scan. `cast` now ships the same way after a successful build (push, creating the upstream if needed). Pass `no-pr` to stop after the commit. When attach cannot run, the PR still opens and the script prints why.

## 0.9.0

- `mend` and the Weaver agent: finish an in-progress merge, rebase, cherry-pick, or revert by reading both sides of each hunk, keeping both intents when they commute, running the project's checks, and continuing the git operation. Never aborts. Inspired by the merge-conflict skill in mattpocock/skills (MIT), written from scratch.

## 0.8.2

- `cast` loads a spec path or the conversation before writing intent, stages only this session's diff, and classifies suite failures against the pre-change baseline. `map.sh` passes `--repo` on every `gh issue` and `gh label` call, and label create fails through to exit 3 unless the label already exists. `scry` examples set `GH_HOST`. `sift` will not apply a state-only override until the issue has one category.

## 0.8.1

- `map.sh`: a 403 on attach or wire writes `Part of #` / `Blocked by:` instead of aborting into a second local map. Frontier discovers children from those links and task-list lines, not every `#N` in the map body. `claim` refuses when someone else already holds the ticket.

## 0.8.0

- `scry`, `cast`, and `sift`: the planning loop I actually run. `scry` charts a GitHub map of decision tickets and walks them one at a time. `cast` builds a ready ticket on the current branch. `sift` moves the inbox through the same triage states. Inspired by the engineering skills in mattpocock/skills (MIT), written from scratch. Existing maps keep the `wayfinder:*` labels.

## 0.7.3

- `scripts/validate.sh` checks that the plugin name agrees across both manifests, that no README slash command points at a skill that does not exist, and that every skill directory is shown in the README.
- The naming convention is written down: the skill name is the spell, the description stays plain English.
- `.mimic.md` is gitignored, since `mimic setup project` writes one into whatever repo it runs in.

## 0.7.2

- The marketplace is named `frankieramirez`, so the install is `mana@frankieramirez`. A marketplace names a publisher, not a product, and it shows up where provenance is the useful thing to know. `mana` carries the brand in every slash command. The plugin name and every skill are unchanged.

## 0.7.1

- The marketplace was briefly `ark`.

## 0.7.0

- The plugin is now `mana` and the marketplace is `mana`, installed from `frankieramirez/mana`. Every skill is renamed after the spell it casts: `wringer` to `scan`, `settle` to `remedy`, `spit` to `dispel`, `be-me` to `mimic`, `scrap` to `banish`. Slash commands become `/mana:scan` and the rest. Frontmatter descriptions are unchanged in meaning, so model invocation still fires on the same plain-English triggers.
- The voice profile moves from `.be-me.md` to `.mimic.md`. Rename any existing file by hand.

## 0.6.0

- `no-comment` renamed to `settle`. The old name read like it was about code comments, which is what `scrap` does, and it named the one rule instead of the job.

## 0.5.0

- `be-me setup` and `be-me refresh`: a new Ghost agent mines the user's own writing (session messages, prompts typed to the coding agent in its local logs, PR comments, PR descriptions, commits) and returns a filled-in voice profile draft for approval. Text written by a tool under the user's name is dropped as evidence.
- `be-me setup` also feeds Ghost the user's own messages to other people, fetched by the skill since Ghost has no browser or connectors: sent messages from a connected chat workspace first, then posts from a public profile the user names. Writing addressed to a person now stays separate from writing addressed to a tool, and work sources get scrubbed before any sample reaches disk.
- `wringer` comment mode reads the voice profile when one exists.
- `scripts/sync-agent.sh` generates every agent from a table and gains `--check`.

## 0.4.0

- `address-feedback` renamed to `no-comment`.

## 0.3.0

- `deep-review` renamed to `wringer`.

## 0.2.0

- `decomment` renamed to `scrap`.

## 0.1.1

- `spit`: quote the frontmatter description so skills.sh discovers the skill.

## 0.1.0

First release.

- `deep-review`: multi-reviewer code review with risk-selected personas.
- `address-feedback`: resolve PR review feedback by fixing code, with no PR comments.
- `spit`: strip the essay register from anything a person will read.
- `be-me`: reply to a message as the user, in their voice, without the AI tells.
- `scrap` + Comment Reaper agent: remove comments that do not earn their place.
