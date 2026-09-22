# Capture

Every pull request includes an image or video showing the change or its check output. An attachment alone does not establish that the behavior works. Keep failed checks in the validation record even when their media is omitted from the showcase. Existing validation gates still apply.

`--attach` accepts PNG, JPEG, GIF, WebP, SVG, MP4, MOV, and WebM.

## Preference

Pick the first that applies.

1. A screenshot or short recording of the user-visible change. Use the screenshot or recording tools the host already offers. Inside an Orca worktree (`ORCA_WORKTREE_ID` is set and `command -v orca` succeeds), Orca's embedded browser is one of them; see below.
2. When there is no GUI surface, an SVG of the proving command's actual output (the test run or the CLI invocation). Run `scripts/text-frame.sh` on that output.
3. Last resort: an SVG of the commit subject and an accurately labelled validation result. Label this a summary illustration; it establishes no behavioral outcome. If no check ran, say unrun.

## Evidence record

In the PR body and final report, tie each material claim to its evidence. Use these distinctions:

| Kind | What it establishes |
|------|---------------------|
| Visual demonstration | Only the state or interaction visibly observed; a mockup establishes appearance only |
| Executed verification | The named command or scenario ran against the recorded state, with its actual result |
| Unverified claim | Source inspection, unavailable runtime, an unrun check, or a summary illustration leaves behavior unverified |

For each executed check record the command or scenario, revision (plus relevant working-tree changes), outcome (`passed`, `failed`, `blocked`, or `unrun`), and the claim it supports. A blocked prerequisite is not a passed test. Source inspection can support an implementation assessment but cannot be reported as an executed check.

Reuse evidence only if relevant files and inputs have not changed. After a relevant edit, rerun the check or label its earlier result stale and the current claim unverified. Do not weaken a workflow's shipping gate by relabelling its required check.

Examples, with illustrative revisions:

- Visual demonstration: `settings.png` shows the saved theme at `abc123`; reload persistence was not checked.
- Executed verification: `bash tests/search.sh` at `abc123` exited 0; the empty-query assertion passed.
- Failed verification: the same command exited 7; rendering its output succeeded, but search validation failed.
- Unverified claim: the browser runtime is missing; the interaction check is blocked. The summary SVG supplies no behavioral proof.

## Quality

Use the smallest set that illustrates the observed result. One recording of the flow beats four stills of the same screen.

Keep out:

- The editor, the file tree, and other IDE chrome
- Install steps, login waits, and spinner time
- Duplicate frames of the same state
- A run that failed

Write every file under a fresh private directory, `DIR=$(mktemp -d)`, and pass its absolute path to `--attach` and into the body. Never a fixed path under `/tmp`: another local user can create that file first and control what goes into the pull request. Never `git add` them.

## text-frame.sh

`<SKILL_DIR>` is the absolute directory the `SKILL.md` lives in. Substitute the real path every time it appears. Do not assign it to a shell variable first: a sandboxed or worktree-isolated session refuses `bash "$VAR/script.sh"` because it cannot resolve the path to read the script.

Run this block in Bash. The subshell preserves both statuses even under `set -e`; its exit status prefers the proving command's failure over a renderer failure.

```bash
(
  set +e
  set -o pipefail
  <the proving command> 2>&1 | bash "<SKILL_DIR>/scripts/text-frame.sh" "$DIR/tests.svg"
  capture_status=("${PIPESTATUS[@]}")
  printf 'check_exit=%s render_exit=%s\n' "${capture_status[0]}" "${capture_status[1]}" > "$DIR/status.txt"
  if [ "${capture_status[0]}" -ne 0 ]; then exit "${capture_status[0]}"; fi
  exit "${capture_status[1]}"
)
```

The script reads stdin and writes a dark monospace SVG. It XML-escapes the text and strips ANSI color codes. Long lines wrap. Cap the input at what the command actually printed.

Name the file for what it shows (`tests.svg`, `cli-search.svg`).

## Orca's embedded browser

Only inside an Orca worktree. Open the page, reach the state, and capture:

```bash
orca tab create --url <url> --json      # only when screenshot reports browser_no_tab
orca goto --url <url> --json
orca snapshot --json                    # element refs like @e3 for click and fill
orca click --element @e3 --json
orca screenshot --json | python3 -c 'import base64,json,sys; open(sys.argv[1],"wb").write(base64.b64decode(json.load(sys.stdin)["result"]["data"]))' "$DIR/feature.png"
```

`full-screenshot` captures beyond the viewport. The JSON carries the image as base64 under `result.data`; the one-liner writes it to a file. `DIR` is the temp directory from `mktemp -d`. The tab has to be visible in the app: a `Screenshot timed out` error means the browser pane is hidden or another worktree is in front, and `orca tab switch --index 0 --json` is the one retry worth making. A call that still fails falls through to the next preference; it is never a stop.
