# Working in this repo

This is Frankie Ramirez's personal skills repo. It is both a Claude Code plugin (`mana`, marketplace `frankieramirez`) and a skills.sh source. One layout serves both: `skills/<name>/SKILL.md` plus `agents/`.

## Conventions

- Every `SKILL.md` has frontmatter with `name` equal to its directory name and a `description` that says when to use it, including the trigger phrases a user would type.
- A skill is named for the spell it casts (`scan`, `remedy`, `dispel`, `mimic`, `banish`, `scry`, `cast`, `sift`, `mend`, `reveal`, `augur`, `conjure`). The one exception is `setup-mana`, named for what a new user would type. The name is flavour and only has to be typed. The `description` is what the model matches on, so it stays plain English, names the job, and lists the words a user would actually say. Never put the theme in a description, because nobody asks to have their prose dispelled.
- Ship files (`capture.md`, `body.md`, `attach.md`, `open-pr.sh`, `text-frame.sh`) live under `skills/reveal/` and are copied to `skills/cast/`. Edit the reveal copies; `scripts/validate.sh` checks they match.
- Ticket files (`agent-brief.md`, `tickets.sh`) live under `skills/sift/` and are copied to `skills/conjure/`, `skills/cast/`, and `skills/setup-mana/`. Edit the sift copies; the same script checks they match. Every label, issue, edge, claim, and `next` lookup on the tracker goes through `tickets.sh`, never a hand-written `gh issue` call.
- The tracker is whatever `docs/agents/issue-tracker.md` in the user's repo says: GitHub, Linear, Jira, local files, or prose the user wrote. `setup-mana` writes that file from the templates under `skills/setup-mana/references/`. A skill that touches tickets reads the file first and passes its `Adapter flags:` to `tickets.sh`.
- Prose follows the `dispel` skill: no em or en dashes, no "not X but Y", no rule of three, lead with the point. `scripts/validate.sh` fails on dashes.
- A skill's supporting files live in `references/` and are loaded by stage, not all at once. Name the stage that loads each one inside `SKILL.md`.
- Scripts under `skills/*/scripts/` are bash. The GitHub paths depend only on `git` and `gh`. The Linear and Jira paths inside `tickets.sh` use `python3` with the standard library and nothing else. No jq binary, no node, no pip packages.
- Everything under `agents/` is generated. Edit the reference file named in the table in `scripts/sync-agent.sh` (`skills/banish/references/comment-reaper.md`, `skills/mimic/references/ghost.md`, `skills/mend/references/weaver.md`) and run that script. Adding an agent means a new table row plus a line in `plugin.json`.
- Every behavior change bumps `version` in `.claude-plugin/plugin.json` and gets a line in `CHANGELOG.md`. Claude Code caches plugins by version, so a change without a bump does not reach installed copies.
- Nothing here references another plugin, marketplace, or skill by name. Skills must work standalone under Codex, Cursor, or Copilot where only the `SKILL.md` and its folder are installed.

## Checks

- `scripts/validate.sh` before every commit. CI runs the same script.
- `scripts/similarity.py` when touching `scan` or `remedy`: those started as forks and the rewrite is only done while every ratio stays under 0.30.

## Local development

`scripts/link-local.sh` symlinks this checkout into `~/.claude/skills` and `~/.claude/agents`. Uninstall the `mana` plugin first (`claude plugin uninstall mana@frankieramirez`) or every skill appears twice.
