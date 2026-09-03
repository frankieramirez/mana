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

Skills are then invoked as `/mana:scan`, `/mana:remedy`, `/mana:dispel`, `/mana:mimic`, `/mana:banish`, `/mana:scry`, `/mana:cast`, `/mana:reveal`, `/mana:sift`, `/mana:mend`.

**Everything else** via [skills.sh](https://skills.sh):

```
npx skills add frankieramirez/mana            # this project
npx skills add frankieramirez/mana -g         # every project on this machine
npx skills add frankieramirez/mana -a codex   # one agent only
```

## Skills

### scan

Multi-reviewer code review for a branch or PR. Picks a roster of reviewer personas from what the diff actually touches (correctness always, then security, performance, data migration, API contract, reliability, testing, maintainability, adversarial, frontend races, project standards as warranted), runs them in parallel as subagents that return structured findings, merges and deduplicates, and renders one report. Ends with a single question: report only, fix and push, or leave inline PR comments in your own voice.

```
/mana:scan                    # current branch against its base
/mana:scan 123 report         # PR 123, report only
/mana:scan base:main fix      # diff against main, fix everything actionable
```

### remedy

Resolves review feedback already on a PR. Fetches every unresolved thread, top-level comment, and review body, judges each one centrally (bots and humans alike), fixes what is real in parallel subagents, validates once, commits, pushes, and resolves the handled threads. It never writes to the PR conversation. Anything it would have said goes into the summary for you to paste or ignore.

```
/mana:remedy               # the current branch's PR
/mana:remedy 123 dry-run   # judge and plan only
/mana:remedy <comment-url> # one thread
```

### dispel

Rewrites anything a person will read (Slack messages, PR descriptions, tickets, docs, commit bodies) so it sounds like someone talking. Bans the essay register: em dashes, antithesis, rule of three, setup and payoff, hedging, performed enthusiasm. Triggers on "no em dashes", "sounds like AI", "make it sound human", "strip the AI voice".

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

Charts a chunk of work too big for one session as a GitHub map of decision tickets, then walks the frontier one ticket at a time. Charting names the destination, files the questions that are already sharp, and fires research in parallel. Walking claims the next unblocked ticket, resolves it, and files whatever the answer made specifiable. Tracker labels stay `wayfinder:map` and `wayfinder:<type>` so maps you already have keep working. If GitHub refuses the write (403), the same shape lands under `.scratch/<slug>/`.

```
/mana:scry                        # chart a map from the idea in the conversation
/mana:scry 92                     # walk map #92, or claim ticket #92
/mana:scry 92 you-pick            # accept recommended answers
```

### cast

Builds one ready ticket or spec on the current branch. Loads an agent brief when the issue has one, red-greens at named seams when the repo has tests, checks the diff against the ticket, and commits. Then pushes (creating the upstream if needed) and opens a pull request with visual evidence. Pass `no-pr` to stop after the commit. Stays off other branches.

```
/mana:cast                        # the ticket already in this conversation
/mana:cast 181                    # GitHub issue 181
/mana:cast 181 no-pr              # commit only
```

### reveal

Opens or updates a pull request for the current branch and puts a screenshot, recording, or command-output image in the description. Uses `gh --attach` so the file lands inline. A docs or backend change still gets a file: an SVG of the proving command. Stays off other branches.

```
/mana:reveal                      # current branch
/mana:reveal 42                   # PR 42, if its head is this branch
```

### sift

Moves unlabeled and `needs-triage` issues through the existing inbox states (`needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`). Verifies the claim, grills when the request is thin, and posts an agent brief when the work can be delegated. Rejected enhancements land in `.out-of-scope/`. Tracker comments start with a triage disclaimer.

```
/mana:sift                        # what needs attention
/mana:sift 42                     # one issue
/mana:sift move 42 to ready-for-agent
```

### mend

Finishes an in-progress merge, rebase, cherry-pick, or revert that has unmerged paths. Reads both sides of every hunk, keeps both intents when they commute, runs the project's checks, and continues the git operation. It never aborts. Weaver is the agent that resolves the hunks; the skill audits, regenerates lockfiles, and finishes the sequence.

```
/mana:mend                        # the conflicted merge or rebase already in progress
```

## Layout

```
.claude-plugin/    plugin.json and marketplace.json
skills/<name>/     SKILL.md, references/, scripts/
agents/            Claude Code subagents (generated, see CLAUDE.md)
scripts/           validate.sh, sync-agent.sh, link-local.sh, similarity.py
```

## Acknowledgements

`scan` and `remedy` began as forks of the review skills in Every's [compound-engineering](https://github.com/EveryInc/compound-engineering-plugin) plugin (MIT) and were rewritten from there. `banish` and its Comment Reaper agent were inspired by the `no-comments` skill and Comment Sicko agent in [pstack](https://github.com/cursor/plugins/tree/main/pstack), from Cursor's plugin collection (MIT). Both were written from scratch here, but the idea of handing a diff to an agent that hates comments and then acting on what it finds is theirs.

`scry`, `cast`, `sift`, and `mend` were inspired by the engineering skills in [mattpocock/skills](https://github.com/mattpocock/skills) (MIT) and written from scratch here. Existing GitHub maps keep the `wayfinder:*` labels that loop already shipped.

## License

MIT
