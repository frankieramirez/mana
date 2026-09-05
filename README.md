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

Agent skills I use across personal and work projects. They work in Claude Code as a plugin and in agents that read `SKILL.md` files, including Codex, Cursor, Copilot, and Gemini CLI.

[Install](#install) · [The loop](#the-loop) · [Skills](#skills) · [Trackers](#trackers) · [Unattended](#unattended) · [Orca](#orca)

## Install

**Claude Code** (plugin, includes the Comment Reaper, Ghost, and Weaver agents):

```
/plugin marketplace add frankieramirez/mana
/plugin install mana@frankieramirez
```

Invoke a skill by name, for example `/mana:scan` to review the current branch.

**Everything else** via [skills.sh](https://skills.sh):

```
# This project
npx skills add frankieramirez/mana

# Every project on this machine
npx skills add frankieramirez/mana -g

# One agent only
npx skills add frankieramirez/mana -a codex
```

## The loop

Start with [setup-mana](#setup-mana) for a new repo, [scry](#scry) for an idea, [sift](#sift) for an incoming report, or [cast](#cast) for a ready ticket.

| Stage | Skill | What it leaves behind |
|-------|-------|-----------------------|
| Set up a repo | [setup-mana](#setup-mana), [attune](#attune) | Tracker configuration and repo defaults |
| Decide | [scry](#scry) | A decision map and a spec |
| Triage the inbox | [sift](#sift) | Issues sorted by state, ready ones with an agent brief |
| File the build tickets | [conjure](#conjure) | Session-sized tickets in build order |
| Build | [cast](#cast) | A committed change and a PR with proof |
| Review | [scan](#scan), [augur](#augur) | Findings, optional fixes, and evidence the change is safe |
| Answer feedback | [remedy](#remedy), [mimic](#mimic) | Resolved feedback and paste-ready replies |
| Repair along the way | [mend](#mend), [banish](#banish), [reveal](#reveal), [dispel](#dispel) | Finished merges, fewer comments, PR bodies, and edited prose |

Build work meets at a `ready-for-agent` issue with an agent brief. A person merges the PR; [tracker closing rules](#trackers) determine when the ticket closes. `cast next` picks up the next ready ticket.

After setup, use `sift` for incoming work and `cast next` for ready tickets. Review PRs with `scan`, handle feedback with `remedy`, and use `augur` when a small diff looks risky.

## Skills

### setup-mana

Configures a repository so the other skills know where tickets live and how to check their work.

- Records the tracker choice and configures triage labels.
- Runs a detected validation command and writes repo instructions.

```
# Reuse the choice, or ask once
/mana:setup-mana

# Choose Linear without the question
/mana:setup-mana linear
```

<details>
<summary>Setup details and additional commands</summary>

Setup detects the remote, existing docs and labels, a test command, tracker variables, and live connectors. It reuses the latest explicit tracker choice or the choice saved in `docs/agents/issue-tracker.md`. With no choice yet, it asks where tickets live; the detected option appears first and is marked as detected. A GitHub remote alone never settles the choice. If you request a switch without naming the destination, it asks for one.

Choose from the [supported trackers](#trackers), or describe your own in a paragraph. Re-run setup and name the tracker to switch trackers. Use [attune](#attune) to change another setting later.

| Setup output | What happens |
|--------------|--------------|
| `docs/agents/issue-tracker.md` | Records the tracker and its conventions |
| Triage labels | Ensures the seven roles have labels after the tracker check passes; local and custom trackers skip this step |
| `docs/agents/triage-labels.md` | Records a mapping when setup reuses existing label names |
| `## Agent skills` block | Updates the existing `CLAUDE.md` or `AGENTS.md`; creates `AGENTS.md` when neither exists |
| Validation command | Runs the detected command once; omits it if a missing binary or startup failure prevents tests |

Proof capture and domain docs keep their defaults. Setup leaves the peer reviewer unset; use `attune peer` to configure one.

A missing Linear or Jira credential still allows setup to write the configuration. The report marks the check unverified and names the variable to set. Once it is available, `attune key` verifies the tracker.

```
/mana:setup-mana you-pick   # take the detected tracker
```

</details>

### attune

Changes one repo setting after setup and shows which skills read it.

- Run it bare to see current values and choose a setting.
- Name the setting and value to write it without a question.

```
# List settings and current values
/mana:attune

# Change the validation command
/mana:attune validation
```

<details>
<summary>Available settings and additional commands</summary>

| Setting | What it changes |
|---------|-----------------|
| `labels` | Names for the seven triage roles; creates missing tracker labels |
| `validation` | The `Validation:` line, after the command runs clean |
| `proof` | How pull request proof gets captured |
| `docs` | Single context (`CONTEXT.md`) or multi context (`CONTEXT-MAP.md`) |
| `peer` | The installed CLI that receives the diff for a second opinion on every review |
| `worktree` | `.worktreeinclude` and `orca.yaml` for fresh Orca worktrees |
| `pr-surface` | Whether external GitHub PRs enter triage as requests with attached code |
| `key` | The Linear team or Jira project key; verifies it against the tracker |
| `pointer` | Whether the instructions block lives in `CLAUDE.md` or `AGENTS.md` |

Every setting has a default, so removing a setting is allowed. To switch trackers, re-run [setup-mana](#setup-mana) with the new tracker name.

**Setting `peer` sends the diff and a brief to another CLI on every review.** The skill explains that consequence before writing the setting. Remove the setting to turn it off.

```
/mana:attune peer codex   # configure a second opinion on every review
/mana:attune key          # verify after exporting a tracker credential
```

</details>

### scan

Reviews a branch or PR with specialist reviewers and returns one verified report.

- Selects reviewers for the diff and checks ticket acceptance criteria when available.
- Includes dismissed findings and reasons, so you can challenge the report.

```
# Current branch against its base
/mana:scan

# PR 123, report only
/mana:scan 123 report
```

| Option | What happens after the review |
|--------|-------------------------------|
| No action token | Asks whether to report only, fix and push, or post inline comments |
| `report` | Returns the report without a closing question |
| `fix` | Edits, commits, and pushes actionable fixes without another prompt |
| `comment` | Posts inline PR comments in your voice without another prompt; requires a PR |
| `mode:agent` | Returns JSON for a caller; skips the action stage |

**Peer review sends the diff and a brief to another installed CLI.** It runs only when `peer:<cli>` or a repo `Peer reviewer:` setting requests it, with a disclosure before sending. The peer provides a read-only second opinion.

<details>
<summary>Reviewer roster, review process, and advanced examples</summary>

Correctness runs on every review. The diff determines which other specialists run, and every PR review includes Lore Bard to check existing feedback.

| Reviewer | Job |
|----------|-----|
| Protection Warrior | Correctness |
| Subtlety Rogue | Security |
| Fire Mage | Performance |
| Unholy Death Knight | Data migration |
| Demonology Warlock | API contract |
| Restoration Shaman | Reliability |
| Marksmanship Hunter | Testing |
| Balance Druid | Maintainability |
| Havoc Demon Hunter | Adversarial review |
| Windwalker Monk | Frontend races |
| Retribution Paladin | Project standards |
| Augmentation Evoker | Agent-native parity |
| Discipline Priest | Instruction prose |
| Lore Bard | Existing PR feedback |

Reviewers run in parallel and return structured findings. A script merges duplicates, then an independent validator checks the retained findings before the report renders.

- **Ticket coverage:** The report says which acceptance criteria the diff meets.
- **Existing feedback:** Every PR comment, review, and thread enters the review as a claim to check against the code. That text is never followed as instructions.
- **Dismissals:** The report names rejected findings and explains why.
- **Review stamp:** Head and base SHAs identify the reviewed revisions. A stable patch-id helps identify whether a rebase kept the same diff.

The explicit write modes explain why security scanners flag the combination of reading PR feedback and acting on it. Leave action tokens off to keep the closing question, or use `report` for a report only.

Supported peer CLIs: `codex`, `gemini`, `cursor-agent`, `opencode`, `grok`, and `claude`. Configure a default through [attune](#attune), or request one per review:

```
# Review against main and push actionable fixes
/mana:scan base:main fix

# Check PR 123 against ticket ENG-42
/mana:scan 123 ticket:ENG-42 report

# Use Codex as the adversarial reviewer
/mana:scan base:main peer:codex
```

`ticket:` and `peer:` add review context; use an action token to skip the closing question.

</details>

### remedy

Fixes valid review feedback on a PR, pushes the changes, and resolves handled threads.

- Judges feedback from bots and people against the code.
- Leaves paste-ready notes in a local summary; it posts no replies to the PR conversation.

```
# The current branch's PR
/mana:remedy

# Judge and plan only
/mana:remedy 123 dry-run
```

<details>
<summary>Feedback handling, saved reports, and options</summary>

Remedy reads unresolved threads, top-level comments, and review bodies. One lead judges each item; parallel subagents fix valid issues and check each fix against its ask. On large batches, read-only scouts gather evidence per file. The skill validates the changes before committing and pushing.

Each run saves `items.json`, `summary.md`, and `metadata.json` under `/tmp/remedy-<uid>/`. The next run on that PR reads them to identify reopened threads and decisions still waiting on you.

Failing checks get classified before a fix:

| Failure | Response |
|---------|----------|
| In code the PR touched | Add it to the fix list |
| In untouched code | Check whether the base is stale |
| Suspected flake | Rerun at most once |

`needs-human` items stay in the summary. Use `no-push` to fix locally, or a comment URL to target one thread.

```
/mana:remedy 123 no-push
/mana:remedy <comment-url>
```

</details>

### dispel

Rewrites prose so it sounds like a person talking.

Use it for docs, messages, PR descriptions, or other writing. It also triggers on “no em dashes,” “sounds like AI,” “make it sound human,” and “strip the AI voice.”

```
# Rewrite the prose in context
/mana:dispel
```

<details>
<summary>What the prose pass removes</summary>

- Essay habits: em dashes, antithesis, rule of three, setup and payoff, hedging, and performed enthusiasm.
- Vague language: metaphor nouns such as substrate and vector, passive voice with a nameable actor, adverbs standing in for a number, and sentences that could fit any project's docs.

</details>

### mimic

Drafts a reply in your voice, ready to paste into the conversation.

- Uses your own writing and an optional voice profile to match the medium.
- Returns the reply text; unknown facts get bracketed placeholders.

```
# Reply to the last message
/mana:mimic
```

<details>
<summary>Voice sources, profile setup, and additional commands</summary>

Mimic reads your messages in the thread, a project `.mimic.md` or personal `~/.mimic.md`, and relevant commits or comments in the repo. The profile template lives at `skills/mimic/references/voice-profile.md`. [Scan](#scan) uses the same profile for PR comments.

Replies follow the [dispel](#dispel) prose rules and fit the medium's length. Chat replies skip lists, acknowledgement openers, and helpful closers. Missing facts stay as placeholders.

`setup` spawns Ghost to build a profile from your own writing:

- Local agent logs supply prompts you typed; your PR comments, descriptions, and commits add repo context. Text a tool wrote under your name is excluded.
- Sent messages from a connected Slack workspace show how you write to people. A named public profile, such as X or a blog, works too.
- Work samples are scrubbed before they enter the profile.
- You review and approve the draft before it is written to `~/.mimic.md`, or `.mimic.md` with `project`.

```
/mana:mimic setup                  # build your personal profile
/mana:mimic setup slack            # include your sent Slack messages
/mana:mimic setup x.com/yourhandle  # include your public posts
/mana:mimic setup project          # build this project's profile
/mana:mimic refresh                # rebuild and show the diff
```

You can also give an instruction for the reply:

```
/mana:mimic "say no, we're at capacity until next sprint"
```

</details>

### banish

Removes comments that do not earn their place and fixes the code they were covering for.

```
# Current diff against main
/mana:banish

# One path
/mana:banish src/api/
```

<details>
<summary>Comment review and the keep list</summary>

The Comment Reaper audits the diff. The skill checks its report before deleting comments and repairing the code.

Comments survive for license headers, public API contracts, quirks in third-party code we cannot change, formatter directives, style-only lint suppressions, and links to constraints the code cannot express.

</details>

### scry

Turns work too large for one session into a map of decision tickets, then resolves them one at a time.

- Charting starts from the goal and researches questions in parallel.
- Walking claims the next unblocked ticket and files new questions as answers emerge.

```
# Chart the idea in the conversation
/mana:scry

# Walk map #92, or claim ticket #92
/mana:scry 92
```

<details>
<summary>Decision records, tracker labels, and unattended use</summary>

The map lives on GitHub, with project context in `CONTEXT.md`, decision records in `docs/adr/`, and a spec for the build. Charting files questions that are ready to investigate; walking resolves one and files whatever its answer makes specific enough to tackle.

Tracker labels are `scry:map` and `scry:<type>`. Existing maps with `wayfinder:*` labels still work. If GitHub refuses a write with 403, the same map structure lands under `.scratch/<slug>/`.

```
/mana:scry 92 you-pick   # accept recommended answers
```

</details>

### conjure

Turns a finished map, spec, or conversation plan into build tickets in dependency order.

- Each ticket is a session-sized vertical slice with an agent brief and blocking dependencies.
- Shows the proposed slices and order before filing; `you-pick` accepts the recommendation.

```
# Create tickets from a spec
/mana:conjure docs/spec.md

# Use the plan in this conversation
/mana:conjure you-pick
```

<details>
<summary>Map handoff and write fallback</summary>

On a decision map, conjure posts the build order as a comment. If the token cannot create issues, it saves the same tickets under `.scratch/<slug>/tickets/`.

```
/mana:conjure 92   # file build tickets once the map is decided
```

</details>

### cast

Builds one ready ticket or spec, commits the change, and opens a PR with visual proof.

- Claims the ticket first so another session skips it.
- Pushes and opens the PR by default. With `no-pr`, it skips the PR and pushes only if the branch already has an upstream.

```
# Oldest unblocked ready ticket
/mana:cast next

# Build issue 181 without opening a PR
/mana:cast 181 no-pr
```

<details>
<summary>Branch handling, validation, and additional commands</summary>

Cast uses the current branch. Starting on the default branch creates `cast/<number>-<slug>` before any edit; it never switches to an existing branch. An Orca worktree already has its branch.

The build loads the agent brief when available and uses TDD at named seams for meaningful behavior changes when a test harness exists. Required project checks still run; successful validation is reused when no later edit or unresolved concern needs a fresh run. It checks the diff against the ticket before committing, then pushes, creating an upstream if needed.

The PR includes visual evidence and the [tracker's closing line](#trackers). In [Orca](#orca), the ticket, status, and PR also appear on the worktree card.

```
/mana:cast       # ticket or spec already in the conversation
/mana:cast 181   # GitHub issue 181, including the PR
```

</details>

### reveal

Opens or updates a PR for the current branch with a scannable description and visual proof.

- The body combines a short explanation with a compact tree or structural diff.
- Proof can be a screenshot, recording, or command-output image. Docs and backend changes get an SVG of the proving command.

```
# Current branch
/mana:reveal

# PR 42, if its head is this branch
/mana:reveal 42
```

It uses `gh --attach` for inline proof and stays on the current branch. If attachment is refused, it still opens the PR and explains why.

### sift

Triages incoming issues and adds an agent brief when the work is ready to delegate.

- Uses the configured tracker and checks the claim before assigning a state.
- `you-pick` handles up to 10 issues per run and leaves rejection decisions for a person.

```
# Find what needs attention
/mana:sift

# Triage unattended
/mana:sift you-pick
```

<details>
<summary>Inbox states and targeted commands</summary>

Sift starts with unlabeled and `needs-triage` issues, moving them through `needs-info`, `ready-for-agent`, `ready-for-human`, or `wontfix`. It asks for detail when a request is thin and puts rejected enhancements in `.out-of-scope/`. Tracker comments start with a triage disclaimer.

It works on GitHub, Linear, Jira, or local files according to the tracker file. Under `you-pick`, it never closes an issue as rejected.

```
/mana:sift 42                       # one GitHub issue
/mana:sift ENG-42                   # one Linear issue
/mana:sift move 42 to ready-for-agent
```

</details>

### mend

Finishes a conflicted merge, rebase, cherry-pick, or revert while preserving both sides' intent where possible.

Weaver resolves the hunks; the skill audits the result, regenerates lockfiles, and runs the project's checks before continuing the git operation. It never aborts the operation.

```
# Finish the conflicted operation
/mana:mend
```

### augur

Finds what a change could break beyond its diff and runs code to prove the fact that makes it safe.

- Traces dependencies beyond text search, including wire formats and distant callers.
- Leaves the proving script on disk so a reviewer can rerun it.

```
# Current branch against its base
/mana:augur

# PR 123, without checking it out
/mana:augur 123
```

<details>
<summary>Evidence levels and targeted checks</summary>

Augur names one fact the change is safe because of and moves it through five evidence levels: asserted, cited, walked, ran, reproduced. Anything below “ran it” stays unproven.

The search includes pinned library source, wire formats, database columns, feature flags, and callers three hops out.

```
/mana:augur base:main src/cache/   # check one path against main
```

</details>

## Trackers

Tickets use the tracker you choose; pull requests stay on GitHub.

| Tracker | Where tickets live |
|---------|--------------------|
| GitHub Issues | The repository's issues |
| Linear | A Linear team |
| Jira Cloud | A Jira project |
| Local files | Markdown under `.scratch/` |
| Your own tracker | Follow the conventions you describe in a paragraph |

[Setup-mana](#setup-mana) records the choice in `docs/agents/issue-tracker.md` and reuses the latest explicit or saved choice. It asks when the choice is missing or a switch has no named destination. The GitHub remote alone never selects the tracker. Ticket skills read that file before acting.

<details>
<summary>Credentials, connectors, and missing keys</summary>

When the host exposes a Linear or Jira connector, skills use it without a separate API key. Inside an Orca worktree, `orca linear` serves as the Linear connector.

Otherwise, `tickets.sh` provides the same eleven operations across GitHub, Linear, and Jira:

| Tracker | Authentication for the script |
|---------|-------------------------------|
| GitHub | `gh` logged in |
| Linear | `LINEAR_API_KEY` |
| Jira | `JIRA_BASE_URL`, `JIRA_EMAIL`, and `JIRA_API_TOKEN` |

Credentials come from the environment and are never written to a file. Set them wherever a scheduled agent runs.

A missing credential allows setup to record the choice and report what is missing. Set the named variable, then run `/mana:attune key` to verify the tracker.

</details>

<details>
<summary>PR closing rules</summary>

`scan`, `remedy`, and `reveal` keep their GitHub PR workflow with any tracker. A person merges the PR.

| Tracker | PR body | What closes the ticket |
|---------|---------|------------------------|
| GitHub | `Closes #42` | Merge |
| Linear | `Closes ENG-42` | Merge |
| Jira | `Closes PLAT-42` | An automation rule that reads the closing line |
| Local files | Name the ticket file | The builder sets `Status: closed`; merge leaves it unchanged |

</details>

## Unattended

Use explicit tokens to run skills without waiting for answers. Point each scheduled run at one skill; a run with nothing to do exits quietly.

<details>
<summary>Unattended tokens and scheduling examples</summary>

| Skill | Token | What happens |
|-------|-------|--------------|
| `setup-mana` | `you-pick` or a tracker name | Uses the detected or named tracker and writes defaults; reports missing variables. With no explicit choice and nothing detected, writes nothing and reports the missing choice |
| `attune` | `<setting> <value>` | Writes that setting without a question |
| `scry` | `you-pick` | Accepts recommended answers while charting or walking |
| `sift` | `you-pick` | Triages up to 10 issues; leaves rejections for a person |
| `conjure` | `you-pick` | Accepts the recommended slices and order |
| `cast` | `next` | Claims the oldest ready, unblocked ticket and builds its PR; stops when none is ready |
| `scan` | `report`, `fix`, or `comment` | Reports, pushes fixes, or posts PR comments without a closing question |
| `scan` | `mode:agent` | Returns JSON and leaves action to the caller |
| `remedy` | `dry-run` or `no-push` | Judges only, or fixes without pushing; leaves `needs-human` items in the summary |
| `augur`, `mend`, `banish`, `reveal` | None needed | Ask nothing |

For setup, a tracker name is `github`, `linear`, `jira`, or `local`. For scan, `ticket:<id>` and `peer:<cli>` add context; neither skips the action question by itself. See [scan](#scan) for write modes and peer disclosure.

If a token cannot write issues (403), `scry` and `conjure` save the same structure under `.scratch/` and say so. `cast` and `reveal` still open the PR when `--attach` is refused and explain why.

```
# On a laptop, while you do something else
/loop 30m /mana:cast next
/loop 30m /mana:scan fix

# As scheduled agents
nightly       /mana:sift you-pick
on a new PR   /mana:scan <pr> report
on a review   /mana:remedy <pr>
```

</details>

## Orca

[Orca](https://github.com/stablyai/orca) is optional. Inside its worktrees, skills can update worktree cards and capture browser proof. Failed Orca calls are reported while the skill continues.

<details>
<summary>Worktree integration and automation example</summary>

Skills detect Orca through `ORCA_WORKTREE_ID` and the `orca` command on the path.

| Integration | Behavior |
|-------------|----------|
| Worktree cards | `cast` links the claimed ticket. `cast` and `reveal` move the card to in review with the PR URL. |
| Browser proof | `cast` and `reveal` can use `orca screenshot`. |
| Linear | `sift`, `conjure`, and `cast` use `orca linear` without `LINEAR_API_KEY`. `cast` also attaches the PR to the issue. |
| Base branch | `scan` and `reveal` use Orca's base from git config before the default branch. |
| Worktree setup | `attune worktree` writes `.worktreeinclude` and `orca.yaml` so validation can run. `setup-mana` reports when they are needed. |

Orca creates each worktree on its own branch off the base, so `cast` uses that branch. Automations start a new worktree per run and skip runs whose precheck fails:

```
orca automations create --name "cast next" --trigger hourly --provider claude \
  --repo path:. --prompt "/mana:cast next" \
  --precheck "bash <skill dir>/scripts/tickets.sh next ready-for-agent | grep -q ."
```

`<skill dir>` is where `cast` is installed. The same pattern runs `sift you-pick` nightly, or `scan <pr> report` hourly with a precheck that lists open PRs.

</details>

## Layout

```
.claude-plugin/    plugin.json and marketplace.json
skills/<name>/     SKILL.md, references/, scripts/
agents/            Claude Code subagents (generated, see CLAUDE.md)
scripts/           validate.sh, sync-agent.sh, link-local.sh, similarity.py
```

## Acknowledgements

- [Every's compound-engineering](https://github.com/EveryInc/compound-engineering-plugin) (MIT): `scan` and `remedy` began as forks of its review skills and were rewritten here.
- [Cursor's pstack](https://github.com/cursor/plugins/tree/main/pstack) (MIT): `no-comments` and Comment Sicko inspired `banish` and Comment Reaper. Its `blast-radius` inspired `augur`'s safety fact and evidence ladder; `unslop` inspired `dispel`'s plain-speech rules; `interrogate` inspired `scan`'s Dismissed section. These implementations were written from scratch.
- [mattpocock/skills](https://github.com/mattpocock/skills) (MIT): inspired `scry`, `cast`, `sift`, and `mend`, all written from scratch here.
- [humanlayer/skills](https://github.com/humanlayer/skills) (MIT): `show-me` inspired `reveal`'s scannable PR bodies, including trees, call stacks, and structural diffs. The implementation was written from scratch.

## License

MIT
