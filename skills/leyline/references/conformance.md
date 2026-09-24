# Conformance

Load this file in the Conformance stage. The checker is `conform.sh` in this skill's `scripts/` folder. It prints JSON; read it, then report in plain words.

## Static

```bash
bash "<SKILL_DIR>/scripts/conform.sh" static <repo>
```

Reads files only. Safe on any checkout, including one you have not been asked to run. Exit 0 conformant, 1 not.

Each finding has a `rule`, a `severity`, a `path`, and a `message`. Errors break conformance; warnings are worth fixing but do not. Group findings by rule when reporting, and for each group give the smallest change that clears it:

| Rule | Usual fix |
|---|---|
| `control.pointer` | Add `Control: <path>` to the `## Agent skills` block, pointing at the control skill |
| `control.command` | Add a `Command:` line to the control skill |
| `feature.knowledge` | Add `knowledge`. Use `proposed` for anything drafted from code; only a person makes it `confirmed` |
| `feature.reach` | Add `reach` entries, or routes and steps on a scenario |
| `feature.source-roots` | Repair or remove the stale path. An empty list is a warning when the CLI derives sources |
| `feature.scenarios` | Add a scenario record for the feature |
| `scenario.binding` | Wrap the test that proves it in a literal `scenario('<id>', ...)` call |
| `scenario.orphan-binding` | Add the missing record, rename the registration, or narrow `Bindings:` to exclude fixture code |
| `record.results` | Remove stored outcomes from records; results live in run reports |
| `break.none`, `break.orphan` | Write one break patch per important scenario, named by scenario id |

Never mark a feature `confirmed` yourself, and never change a record to match what the code happens to do today. Those are the user's decisions.

## Report

```bash
bash "<SKILL_DIR>/scripts/conform.sh" report <report.json> --exit <code>
```

Validates one saved run report. Pass the exit code the CLI actually returned; a report that disagrees with its own process is the lie this catches.

## Dynamic

```bash
bash "<SKILL_DIR>/scripts/conform.sh" dynamic <repo> --trust --feature <id>
```

Runs the project's own CLI, so it needs the user's agreement first; say what will run and roughly how long it takes. It builds a worktree of HEAD, runs `Prepare:` when declared, then probes:

| Probe | Passes when |
|---|---|
| `list` | Exit 0 with JSON naming every feature record |
| `describe` | Exit 0 with JSON |
| `unknown` | An unknown feature exits 2 |
| `baseline` | The feature run exits 0 with a valid report |
| `break` | The declared patch makes the run exit 1 with a failed check naming the scenario |
| `restore` | Reverting the patch passes again |
| `parallel` | Two concurrent runs both pass with distinct run ids |

A probe is `blocked` when something it depends on did not happen, such as an incomplete baseline. Blocked is not passed; report what blocked it. Uncommitted changes are not in the worktree, and the output says so under `excludedChanges`.

Pick a feature whose run is affordable. A feature run in a large project can take many minutes, and dynamic mode runs it five times. `--timeout` bounds each command.
