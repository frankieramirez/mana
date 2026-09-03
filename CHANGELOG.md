# Changelog

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
