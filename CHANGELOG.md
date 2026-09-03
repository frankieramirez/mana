# Changelog

## 0.5.0

- `be-me setup` and `be-me refresh`: a new Ghost agent mines the user's own writing (session messages, prompts typed to the coding agent in its local logs, PR comments, PR descriptions, commits) and returns a filled-in voice profile draft for approval. Text written by a tool under the user's name is dropped as evidence.
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
