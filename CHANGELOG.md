# Changelog

## 0.13.2

- `tickets.sh`: a GitHub, Linear, or Jira issue URL is reduced to the tracker id before `view`, `claim`, `wire`, `label`, `comment`, and `close`.
- `tickets.sh next`: GitHub and Linear page every matching ready issue before sorting by `createdAt`, so an older eligible ticket past the first 100 is not starved.

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
