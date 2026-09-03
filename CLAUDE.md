# Working in this repo

This is Frankie Ramirez's personal skills repo. It is both a Claude Code plugin (`mana`, marketplace `frankieramirez`) and a skills.sh source. One layout serves both: `skills/<name>/SKILL.md` plus `agents/`.

## Conventions

- Every `SKILL.md` has frontmatter with `name` equal to its directory name and a `description` that says when to use it, including the trigger phrases a user would type.
- A skill is named for the spell it casts (`scan`, `remedy`, `dispel`, `mimic`, `banish`). The name is flavour and only has to be typed. The `description` is what the model matches on, so it stays plain English, names the job, and lists the words a user would actually say. Never put the theme in a description, because nobody asks to have their prose dispelled.
- Prose follows the `dispel` skill: no em or en dashes, no "not X but Y", no rule of three, lead with the point. `scripts/validate.sh` fails on dashes.
- A skill's supporting files live in `references/` and are loaded by stage, not all at once. Name the stage that loads each one inside `SKILL.md`.
- Scripts under `skills/*/scripts/` are bash and depend only on `git` and `gh`. No jq binary, no node.
- Everything under `agents/` is generated. Edit the reference file named in the table in `scripts/sync-agent.sh` (`skills/banish/references/comment-reaper.md`, `skills/mimic/references/ghost.md`) and run that script. Adding an agent means a new table row plus a line in `plugin.json`.
- Every behavior change bumps `version` in `.claude-plugin/plugin.json` and gets a line in `CHANGELOG.md`. Claude Code caches plugins by version, so a change without a bump does not reach installed copies.
- Nothing here references another plugin, marketplace, or skill by name. Skills must work standalone under Codex, Cursor, or Copilot where only the `SKILL.md` and its folder are installed.

## Checks

- `scripts/validate.sh` before every commit. CI runs the same script.
- `scripts/similarity.py` when touching `scan` or `remedy`: those started as forks and the rewrite is only done while every ratio stays under 0.30.

## Local development

`scripts/link-local.sh` symlinks this checkout into `~/.claude/skills` and `~/.claude/agents`. Uninstall the `mana` plugin first (`claude plugin uninstall mana@frankieramirez`) or every skill appears twice.
