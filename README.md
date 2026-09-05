# mana

```
                  .       *
          ·           *          ·
       *             †              .
     ·               ║          ·
           *        ═╬═           *
        *            ║      .
    ·          .     ║               ·
      ╔══════════════╩══════════════╗
      ║                             ║
      ║         M  A  N  A          ║
      ║         ──────────          ║
      ║       test everything       ║
      ║                             ║
      ╚═════════════════════════════╝
          MP [██████████] 100/100
      ·       .                     *
          ┌────── command ──────┐
          │  > Scan             │
          │    Remedy           │  *
          │    Dispel           │
          │    Mimic            │
          │    Banish           │    ·
          │    Scry             │
          │    Cast             │
          │    Reveal           │
          │    Sift             │
          │    Mend             │
          │    Augur            │
          │    Conjure          │
          │    Setup            │
          └─────────────────────┘
           .     *           ·     .
```

Agent skills I use across personal and work projects. They work in Claude Code as a plugin and in any agent that reads `SKILL.md` files (Codex, Cursor, Copilot, Gemini CLI, and the rest of the skills.sh list).

## Install

**Claude Code** (plugin, includes the Comment Reaper, Ghost, and Weaver agents):

```
/plugin marketplace add frankieramirez/mana
/plugin install mana@frankieramirez
```

Skills are then invoked as `/mana:setup-mana`, `/mana:attune`, `/mana:scan`, `/mana:remedy`, `/mana:dispel`, `/mana:mimic`, `/mana:banish`, `/mana:scry`, `/mana:conjure`, `/mana:cast`, `/mana:reveal`, `/mana:sift`, `/mana:mend`, `/mana:augur`.

**Everything else** via [skills.sh](https://skills.sh):

```
npx skills add frankieramirez/mana            # this project
npx skills add frankieramirez/mana -g         # every project on this machine
npx skills add frankieramirez/mana -a codex   # one agent only
```

## The loop

Start where the work is. A repo the skills have not seen starts at `setup-mana`. A new idea starts at `scry`. A bug report from someone else starts at `sift`. Everything meets at a `ready-for-agent` issue with an agent brief, and from there the skills hand off in this order.

| Stage | Skill | What it leaves behind |
|-------|-------|-----------------------|
| Set up a repo | `setup-mana`, `attune` | The tracker choice in `docs/agents/issue-tracker.md`, the triage labels created on it, the validation command, a pointer block in `CLAUDE.md` or `AGENTS.md`; `attune` changes one of those later |
| Decide | `scry` | A map of decision tickets, `CONTEXT.md`, ADRs, a spec |
| Triage the inbox | `sift` | Each issue in one state, `ready-for-agent` ones with a brief |
| File the build tickets | `conjure` | One `ready-for-agent` issue per slice, wired in build order |
| Build | `cast` | A branch, a commit, a pull request with proof and a tracker closing line |
| Review | `scan`, `augur` | A findings report, or the fixes pushed; a proof the change is safe |
| Answer feedback | `remedy`, `mimic` | Fixes pushed, threads resolved, paste-ready replies |
| Repair along the way | `mend`, `banish`, `reveal`, `dispel` | A finished merge, fewer comments, a PR body, prose that reads like you |

A person merges. GitHub and Linear close from the line (`Closes #42`, `Closes ENG-42`). Jira does only when an automation rule reads `Closes PLAT-42`. A local ticket stays open until the builder sets `Status: closed`. `cast next` picks up the one behind it.

An existing project runs setup once and then skips the first two rows. Its steady state is `sift` for what arrives, `cast next` for what is ready, `scan` and `remedy` on every pull request, and `augur` when a small diff looks riskier than its size.

### Trackers

Tickets can live on GitHub Issues, Linear, Jira Cloud, or as markdown files under `.scratch/`. `setup-mana` reuses your tracker choice from the conversation or `docs/agents/issue-tracker.md`, and asks when the choice is missing or you request a switch without naming the destination. `sift`, `conjure`, and `cast` read that file before touching a ticket. A GitHub remote is only a detection signal. On a laptop where the host already exposes a Linear or Jira connector, the skills use it, so no key is needed. Inside an Orca worktree, `orca linear` is such a connector. Everywhere else, one script, `tickets.sh`, does the same eleven operations on all three services. Linear needs `LINEAR_API_KEY`; Jira needs `JIRA_BASE_URL`, `JIRA_EMAIL`, and `JIRA_API_TOKEN`. Both are read from the environment and never written to a file, and a scheduled agent needs them set where it runs. A missing key does not stop setup: the choice is recorded, the report names the variable to set, and `attune key` verifies it once that variable is there. A tracker not on that list still works: describe how it is used in a paragraph and the skills follow that prose.

Pull requests stay on GitHub. `scan`, `remedy`, and `reveal` are unchanged by the tracker choice, and the closing line in a PR body uses the tracker's key (`Closes #42`, `Closes ENG-42`, `Closes PLAT-42`). A local file is named in the body; merge does not rewrite `Status:`.

### Unattended

Every skill that would ask a question has a token that answers it, so the same skill runs from a laptop with a person watching or from a scheduled agent with nobody there.

| Skill | Token | What it does without a person |
|-------|-------|-------------------------------|
| `setup-mana` | `you-pick`, or a bare `github`, `linear`, `jira`, `local` | Takes the detected tracker without asking and writes everything else at its default; an unset variable is reported, never a stop |
| `attune` | `<setting> <value>` | Writes that one setting and asks nothing |
| `scry` | `you-pick` | Accepts every recommended answer while charting or walking |
| `sift` | `you-pick` | Triages up to 10 issues, never closes one as rejected |
| `conjure` | `you-pick` | Accepts the recommended slices and order |
| `cast` | `next` | Claims the oldest ready ticket, branches off the default branch, builds, opens the PR. Nothing ready: says so and stops |
| `scan` | `report`, `fix`, `mode:agent`, `ticket:<id>`, `peer:<cli>` | Skips the closing question; `mode:agent` returns JSON for a caller; `ticket:` names the ticket to verify against; `peer:` adds a second-model reviewer |
| `remedy` | `dry-run`, `no-push` | Judges only, or fixes without pushing; `needs-human` items wait in the summary |
| `augur`, `mend`, `banish`, `reveal` | none needed | Ask nothing |

When the token cannot write issues (a 403), `scry` and `conjure` write the same shape under `.scratch/` and say so. `cast` and `reveal` still open the PR when `--attach` is refused, and say why.

Two shapes that work:

```
# on a laptop, while you do something else
/loop 30m /mana:cast next
/loop 30m /mana:scan fix

# as scheduled agents
nightly       /mana:sift you-pick
on a new PR   /mana:scan <pr> report
on a review   /mana:remedy <pr>
```

Point a routine at one skill per run. A skill that finds nothing to do exits quietly, so a tight schedule costs little.

### Orca

Nothing here needs [Orca](https://github.com/stablyai/orca). When a skill runs inside an Orca worktree (Orca sets `ORCA_WORKTREE_ID` and puts `orca` on the path), it does a little more, and every extra step is best-effort: a failed `orca` call is reported, never a stop.

- `cast` links the ticket to the worktree card after the claim, and moves the card to in review with the PR URL after the ship. `reveal` moves the card the same way.
- `cast` and `reveal` can capture proof from Orca's embedded browser (`orca screenshot`).
- `sift`, `conjure`, and `cast` treat `orca linear` as a Linear connector, so no `LINEAR_API_KEY` is needed there. `cast` also attaches the PR to the Linear issue.
- `scan` and `reveal` read the base branch Orca records in git config before falling back to the default branch.
- `attune worktree` writes `.worktreeinclude` and `orca.yaml`, so a fresh worktree can run the validation command. `setup-mana` says in its report when they are needed.

Orca already creates each worktree on its own branch off the base, so `cast` never makes one there. That fits Orca automations, which run a prompt in a new worktree per run and skip the run when a precheck fails:

```
orca automations create --name "cast next" --trigger hourly --provider claude \
  --repo path:. --prompt "/mana:cast next" \
  --precheck "bash <skill dir>/scripts/tickets.sh next ready-for-agent | grep -q ."
```

`<skill dir>` is wherever `cast` is installed. The same shape runs `sift you-pick` nightly or `scan <pr> report` hourly with a precheck that lists open pull requests.

## Skills

### setup-mana

Sets a repository up for the other skills. It detects the existing configuration and reuses your tracker choice from the conversation or tracker file. With no choice yet, it asks where the tickets live: GitHub Issues, Linear, Jira, markdown files under `.scratch/`, or your own tracker described in a paragraph. The detected answer is listed first and marked as detected. A request to switch trackers asks for a destination only when you have not named one.

Everything else is defaulted and written without asking: `docs/agents/issue-tracker.md`, the seven triage labels created on the tracker, and an `## Agent skills` block in whichever of `CLAUDE.md` or `AGENTS.md` already exists. The validation command is detected, run once, and recorded only when it runs clean. Nothing is written about proof capture, domain docs, or a second reviewer, so a review still sends nothing off the machine unless someone asks for it. A missing Linear or Jira key does not stop it: the choice is recorded and the report names the variable to set. Re-run it to switch trackers, and use `attune` for anything else.

```
/mana:setup-mana                  # reuse the choice, or ask once
/mana:setup-mana linear           # skip the question
/mana:setup-mana you-pick         # take the detected tracker
```

### attune

Changes one setting the other skills read, after setup, without redoing it. Run it bare and it prints every setting with its current value and which skills read it, then asks which one to change. Name a setting to jump straight there, and name a value too and it writes without asking anything.

| Setting | What it changes |
|---------|-----------------|
| `labels` | The label strings the seven triage roles map to, and creates any that the tracker does not have |
| `validation` | The `Validation:` line, after running the command once to prove it works |
| `proof` | How pull request proof gets captured |
| `docs` | Single context (`CONTEXT.md`) or multi context (`CONTEXT-MAP.md`) |
| `peer` | Which installed CLI gets the diff as a second opinion on every review, or removes the line |
| `worktree` | `.worktreeinclude` and `orca.yaml`, so a fresh Orca worktree can run the validation command |
| `pr-surface` | Whether external pull requests enter triage as requests with attached code |
| `key` | The Linear team or Jira project key, then verifies it against the tracker |
| `pointer` | Whether the block lives in `CLAUDE.md` or `AGENTS.md` |

Every setting has a working default and every skill that reads one falls back when it is missing, so removing a setting is always allowed. `peer` prints what leaving the machine means before it writes anything, because that line is the consent. Switching trackers is not here: re-run `setup-mana` for that.

```
/mana:attune                      # list every setting and its current value
/mana:attune validation           # change one, with the current value shown
/mana:attune peer codex           # write it and ask nothing
/mana:attune key                  # re-verify the tracker after exporting a key
```

### scan

Multi-reviewer code review for a branch or PR. Picks a roster of reviewer specs from what the diff actually touches: Protection Warrior (correctness) always, then Subtlety Rogue (security), Fire Mage (performance), Unholy Death Knight (data migration), Demonology Warlock (API contract), Restoration Shaman (reliability), Marksmanship Hunter (testing), Balance Druid (maintainability), Havoc Demon Hunter (adversarial), Windwalker Monk (frontend races), Retribution Paladin (project standards), Augmentation Evoker (agent-native parity), and Discipline Priest (instruction prose) as warranted, plus Lore Bard (existing feedback) on a PR. Runs them in parallel as subagents that return structured findings, merges and deduplicates them with a script, verifies the survivors with an independent validator, and renders one report. When the branch resolves a ticket, the report says which acceptance criteria the diff meets. The report lists what synthesis dismissed and why, so you can override it, and carries a patch-id stamp so a rebase shows up as a different diff. Ends with a single question: report only, fix and push, or leave inline PR comments in your own voice.

Three things to know before pointing it at a PR. It reads every comment, review, and thread on the PR and hands them to a reviewer as claims to check against the code; that text is never followed as instructions, but it does enter the review. The `fix` and `comment` tokens (and `mode:agent`) skip the closing question, so `scan 123 fix` edits, commits, and pushes to the PR branch with no further prompt. Security scanners rate this skill high for exactly that combination. Leave the tokens off when you want the question. And `peer:<cli>` sends the diff to another installed CLI (`codex`, `gemini`, `cursor-agent`, `opencode`, `grok`, or `claude`) as a read-only second opinion; the skill prints one disclosure line before anything leaves the machine, and never does this unless you pass the token or `setup-mana` wrote a `Peer reviewer:` line.

```
/mana:scan                    # current branch against its base
/mana:scan 123 report         # PR 123, report only
/mana:scan base:main fix      # diff against main, fix everything actionable
/mana:scan 123 ticket:ENG-42 report   # PR 123 checked against ticket ENG-42
/mana:scan base:main peer:codex       # Codex as the adversarial reviewer
```

### remedy

Resolves review feedback already on a PR. Fetches every unresolved thread, top-level comment, and review body, judges each one centrally (bots and humans alike), fixes what is real in parallel subagents, checks every fix against its ask, validates once, commits, pushes, and resolves the handled threads. On a large batch, read-only scouts gather the evidence per file while the verdicts stay in one place. Each run leaves `items.json`, `summary.md`, and `metadata.json` under `/tmp/remedy-<uid>/`, and the next run on the same PR reads them so a reopened thread or a decision still waiting on you is named rather than re-judged. It never writes to the PR conversation. Anything it would have said goes into the summary for you to paste or ignore. Failing checks get classified before anything runs: a failure in code the PR touched joins the fix list, a failure in untouched code is checked for a stale base, and a suspected flake gets one rerun at most.

```
/mana:remedy               # the current branch's PR
/mana:remedy 123 dry-run   # judge and plan only
/mana:remedy <comment-url> # one thread
```

### dispel

Rewrites anything a person will read (Slack messages, PR descriptions, tickets, docs, commit bodies) so it sounds like someone talking. Bans the essay register: em dashes, antithesis, rule of three, setup and payoff, hedging, performed enthusiasm. Then the plain-speech pass: metaphor nouns like substrate and vector, passive voice with a nameable actor, adverbs standing in for a number, and sentences that could sit unchanged in any other project's docs. Triggers on "no em dashes", "sounds like AI", "make it sound human", "strip the AI voice".

### mimic

Replies to a message, comment, or email as you, so the other person does not notice you did not type it. Pulls your voice from your own messages in the thread, an optional `.mimic.md` profile (template in `skills/mimic/references/voice-profile.md`), and your commits or comments in the repo. Applies the `dispel` register plus reply rules: match the medium's length, no acknowledgement openers or helpful closers, no lists in chat, no invented facts (a bracketed placeholder instead). Output is the reply text only.

`setup` fills the profile for you. It spawns Ghost, an agent that reads the prompts you have typed to your coding agent in its local logs, plus your own PR comments, PR descriptions, and commits, drops anything a tool wrote under your name, and returns a draft with the evidence. Point it at somewhere you write to people and that goes in too, which matters because everything else on the machine is you talking to a tool. A connected Slack workspace is the best source there is, since your sent messages are the same medium most replies go back into. A public profile (X, Mastodon, Bluesky, a blog) works when there is no connector. Work sources get scrubbed before anything lands in the file. You approve the draft before it is written to `~/.mimic.md`. `scan` reads the same profile when it leaves PR comments.

```
/mana:mimic                          # answer the last message from someone else
/mana:mimic "say no, we're at capacity until next sprint"
/mana:mimic setup                    # build ~/.mimic.md from your own writing
/mana:mimic setup slack              # include your own sent messages from Slack
/mana:mimic setup x.com/yourhandle   # include your own posts from a public profile
/mana:mimic setup project            # build .mimic.md for this project only
/mana:mimic refresh                  # rebuild and show the diff
```

### banish

Removes comments that do not earn their place. Spawns the Comment Reaper on your diff, audits its report, applies the deletions, and then fixes the code the comments were covering for. A comment survives only under a short keep list: license headers, public API contracts, quirks of third-party code we cannot change, formatter directives, style-only lint suppressions, and links to constraints code cannot express.

```
/mana:banish                      # current diff against main
/mana:banish src/api/             # a path
```

### scry

Charts a chunk of work too big for one session as a GitHub map of decision tickets, then walks the frontier one ticket at a time. Charting names the destination, files the questions that are already sharp, and fires research in parallel. Walking claims the next unblocked ticket, resolves it, and files whatever the answer made specifiable. Tracker labels are `scry:map` and `scry:<type>`. Maps that still carry the older `wayfinder:*` labels walk unchanged. If GitHub refuses the write (403), the same shape lands under `.scratch/<slug>/`.

```
/mana:scry                        # chart a map from the idea in the conversation
/mana:scry 92                     # walk map #92, or claim ticket #92
/mana:scry 92 you-pick            # accept recommended answers
```

### conjure

Turns a finished map, a spec, or the plan in the conversation into build tickets. Each one is a vertical slice sized to one session, with an agent brief and the tickets it waits on wired as blocking edges. Presents the slices and a recommended order as one round before filing anything. On a map, posts the build order as a comment. When the token cannot create issues, the same tickets land under `.scratch/<slug>/tickets/`.

```
/mana:conjure 92                  # the map, once nothing is left to decide
/mana:conjure docs/spec.md        # a spec file
/mana:conjure you-pick            # the plan in this conversation, no questions
```

### cast

Builds one ready ticket or spec on the current branch. Claims the ticket first so a parallel session skips it. Starting on the default branch creates `cast/<number>-<slug>` before any edit. Loads an agent brief when the issue has one, red-greens at named seams when the repo has tests, checks the diff against the ticket, and commits. Then pushes (creating the upstream if needed) and opens a pull request with visual evidence and a tracker closing line (`Closes #42`, `Closes ENG-42`, `Closes PLAT-42`; a local file is named in the body). Pass `no-pr` to stop after the commit. Never switches to an existing branch. Inside an Orca worktree the branch already exists, and the ticket, the status, and the PR land on the worktree card.

```
/mana:cast                        # the ticket already in this conversation
/mana:cast 181                    # GitHub issue 181
/mana:cast next                   # the oldest unclaimed ready-for-agent issue
/mana:cast 181 no-pr              # commit only
```

### reveal

Opens or updates a pull request for the current branch. The description is a sentence plus a compact tree or structural diff a reviewer can scan, and a screenshot, recording, or command-output image. Uses `gh --attach` so the file lands inline. A docs or backend change still gets a file: an SVG of the proving command. Stays off other branches.

```
/mana:reveal                      # current branch
/mana:reveal 42                   # PR 42, if its head is this branch
```

### sift

Moves unlabeled and `needs-triage` issues through the existing inbox states (`needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`). Verifies the claim, grills when the request is thin, and posts an agent brief when the work can be delegated. Rejected enhancements land in `.out-of-scope/`. Tracker comments start with a triage disclaimer.

Works on GitHub, Linear, Jira, or local files, whichever the tracker file names. `you-pick` triages without waiting, at most 10 issues per run, and leaves any rejection for a person.

```
/mana:sift                        # what needs attention
/mana:sift 42                     # one issue
/mana:sift ENG-42                 # the same on Linear
/mana:sift move 42 to ready-for-agent
/mana:sift you-pick               # triage the inbox unattended
```

### mend

Finishes an in-progress merge, rebase, cherry-pick, or revert that has unmerged paths. Reads both sides of every hunk, keeps both intents when they commute, runs the project's checks, and continues the git operation. It never aborts. Weaver is the agent that resolves the hunks; the skill audits, regenerates lockfiles, and finishes the sequence.

```
/mana:mend                        # the conflicted merge or rebase already in progress
```

### augur

Finds what a change could break beyond its diff and proves it is safe by running code. Names the one fact the change is safe because of, pushes it up a five-rung evidence ladder (asserted, cited, walked, ran, reproduced), and reports anything below "ran it" as unproven. Looks where grep stops: pinned library source, wire formats, database columns, feature flags, callers three hops out. The proving script is left on disk so a reviewer can rerun it.

```
/mana:augur                       # current branch against its base
/mana:augur 123                   # PR 123, without checking it out
/mana:augur base:main src/cache/  # one path against main
```

## Layout

```
.claude-plugin/    plugin.json and marketplace.json
skills/<name>/     SKILL.md, references/, scripts/
agents/            Claude Code subagents (generated, see CLAUDE.md)
scripts/           validate.sh, sync-agent.sh, link-local.sh, similarity.py
```

## Acknowledgements

`scan` and `remedy` began as forks of the review skills in Every's [compound-engineering](https://github.com/EveryInc/compound-engineering-plugin) plugin (MIT) and were rewritten from there. `banish` and its Comment Reaper agent were inspired by the `no-comments` skill and Comment Sicko agent in [pstack](https://github.com/cursor/plugins/tree/main/pstack), from Cursor's plugin collection (MIT). Both were written from scratch here, but the idea of handing a diff to an agent that hates comments and then acting on what it finds is theirs. The same plugin's `blast-radius` skill inspired `augur` (one safety fact, an evidence ladder, prove it by running code), its `unslop` skill inspired the plain-speech rules in `dispel`, and its `interrogate` lead-judgment notes inspired the Dismissed section in `scan`. All three were written from scratch here.

`scry`, `cast`, `sift`, and `mend` were inspired by the engineering skills in [mattpocock/skills](https://github.com/mattpocock/skills) (MIT) and written from scratch here. Maps filed under that loop's `wayfinder:*` labels still walk.

The scannable PR body in `reveal` (trees, call stacks, structural diffs) was inspired by the `show-me` skill in [humanlayer/skills](https://github.com/humanlayer/skills) (MIT) and written from scratch here.

## License

MIT
