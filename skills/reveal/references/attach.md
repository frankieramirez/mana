# Attach

Ship the pull request with `scripts/open-pr.sh`. That script is the only place that runs `gh pr create` or `gh pr edit` with `--attach`.

## Body

Write the body to a temp file. Lead with what changed and why a reviewer should care. Then the evidence.

Local paths in the Markdown must match the paths you pass as `--attach`:

```markdown
![the settings page after the save](./settings.png)
```

A video that should play as a player sits alone in its paragraph:

```markdown
![](./demo.mp4)
```

Video has no alt text.

## Prose

Write the body the way a person talks.

- Lead with the point.
- No em dashes or en dashes.
- No "not X but Y", no "isn't A, it's B".
- No lists of three for rhythm, no throat clearing, no landing line.
- Contractions are fine.

If the repo has a pull request template (`PULL_REQUEST_TEMPLATE.md`, `.github/PULL_REQUEST_TEMPLATE.md`, `.github/PULL_REQUEST_TEMPLATE/*`, `docs/PULL_REQUEST_TEMPLATE.md`), start from that file and fill it. Keep the evidence section.

## open-pr.sh

```bash
SKILL_DIR="<absolute path of the directory containing this SKILL.md>";
bash "$SKILL_DIR/scripts/open-pr.sh" \
  --title "Title from the branch or ticket" \
  --body-file /tmp/pr-body.md \
  --attach '/tmp/settings.png#the settings page after the save' \
  --attach /tmp/tests.svg
```

`--title` is required when this branch has no pull request yet. The script looks up the current branch's PR. Existing: `gh pr edit --body-file` and `--attach`. None: `gh pr create`.

`--attach` is `path` or `path#alt`. Repeat the flag. Paths must not contain `#`.

The script checks `gh --version` against 2.99.0 and the repo host against github.com. Older CLI, or GitHub Enterprise Server: the PR still opens and attach is skipped. The script prints `attach` as `skipped` and a `reason`. Tell the caller to upgrade `gh`.

Need write access to the repository. Images and GIFs cap at 10 MB. Video caps at 10 MB on Free and 100 MB on paid plans. The script rejects a file over 100 MB and an image over 10 MB.

Prints:

```
action	create|edit
url	https://github.com/OWNER/REPO/pull/N
number	N
attach	yes|skipped
reason	<empty, or why attach was skipped>
```

`--dry-run` prints the same fields plus `command`, checks the files, and does not create or edit.
