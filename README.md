# skills

Agent skills I use across personal and work projects. They work in Claude Code as a plugin and in any agent that reads `SKILL.md` files (Codex, Cursor, Copilot, Gemini CLI, and the rest of the skills.sh list).

## Install

**Claude Code** (plugin, includes the Comment Reaper agent):

```
/plugin marketplace add frankieramirez/skills
/plugin install fr@frankieramirez
```

Skills are then invoked as `/fr:wringer`, `/fr:no-comment`, `/fr:spit`, `/fr:be-me`, `/fr:scrap`.

**Everything else** via [skills.sh](https://skills.sh):

```
npx skills add frankieramirez/skills            # this project
npx skills add frankieramirez/skills -g         # every project on this machine
npx skills add frankieramirez/skills -a codex   # one agent only
```

## Skills

### wringer

Multi-reviewer code review for a branch or PR. Picks a roster of reviewer personas from what the diff actually touches (correctness always, then security, performance, data migration, API contract, reliability, testing, maintainability, adversarial, frontend races, project standards as warranted), runs them in parallel as subagents that return structured findings, merges and deduplicates, and renders one report. Ends with a single question: report only, fix and push, or leave inline PR comments in your own voice.

```
/fr:wringer                    # current branch against its base
/fr:wringer 123 report         # PR 123, report only
/fr:wringer base:main fix      # diff against main, fix everything actionable
```

### no-comment

Resolves review feedback already on a PR. Fetches every unresolved thread, top-level comment, and review body, judges each one centrally (bots and humans alike), fixes what is real in parallel subagents, validates once, commits, pushes, and resolves the handled threads. It never writes to the PR conversation. Anything it would have said goes into the summary for you to paste or ignore.

```
/fr:no-comment               # the current branch's PR
/fr:no-comment 123 dry-run   # judge and plan only
/fr:no-comment <comment-url> # one thread
```

### spit

Rewrites anything a person will read (Slack messages, PR descriptions, tickets, docs, commit bodies) so it sounds like someone talking. Bans the essay register: em dashes, antithesis, rule of three, setup and payoff, hedging, performed enthusiasm. Triggers on "no em dashes", "sounds like AI", "make it sound human", "spit it out".

### be-me

Replies to a message, comment, or email as you, so the other person does not notice you did not type it. Pulls your voice from your own messages in the thread, an optional `.be-me.md` profile (template in `skills/be-me/references/voice-profile.md`), and your commits or comments in the repo. Applies the `spit` register plus reply rules: match the medium's length, no acknowledgement openers or helpful closers, no lists in chat, no invented facts (a bracketed placeholder instead). Output is the reply text only.

```
/fr:be-me                          # answer the last message from someone else
/fr:be-me "say no, we're at capacity until next sprint"
```

### scrap

Removes comments that do not earn their place. Spawns the Comment Reaper on your diff, audits its report, applies the deletions, and then fixes the code the comments were covering for. A comment survives only under a short keep list: license headers, public API contracts, quirks of third-party code we cannot change, formatter directives, style-only lint suppressions, and links to constraints code cannot express.

```
/fr:scrap                      # current diff against main
/fr:scrap src/api/             # a path
```

## Layout

```
.claude-plugin/    plugin.json and marketplace.json
skills/<name>/     SKILL.md, references/, scripts/
agents/            Claude Code subagents (generated, see CLAUDE.md)
scripts/           validate.sh, sync-agent.sh, link-local.sh, similarity.py
```

## Acknowledgements

`wringer` and `no-comment` began as forks of the review skills in Every's [compound-engineering](https://github.com/EveryInc/compound-engineering-plugin) plugin (MIT) and were rewritten from there. `scrap` and its Comment Reaper agent were inspired by the `no-comments` skill and Comment Sicko agent in [pstack](https://github.com/cursor/plugins/tree/main/pstack), from Cursor's plugin collection (MIT). Both were written from scratch here, but the idea of handing a diff to an agent that hates comments and then acting on what it finds is theirs.

## License

MIT
