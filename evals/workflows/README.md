# Workflow eval pilot

Execute a small set of Mana workflows in disposable Git repositories, then inspect their results. This is maintainer tooling. Installed skills do not depend on it.

## Offline checks

```bash
python3 -B evals/workflows/run.py --check
python3 -B -m unittest discover -s evals/workflows -p 'test_*.py'
```

These validate fixtures and graders. They do not execute an agent. Each synthetic grader test supplies known good and bad outcomes, including a nested evidence directory and preservation of an existing Git index.

`cases.json` is the case schema's concrete dataset: unique id, skill, fixture kind, request, allowed effects, expected outcome, and an optional fixture check exit code. The loader validates these fields. `response-schema.json` defines the final report envelope; it does not supply expected answers to the agent. Deterministic graders compare it with command events and repository state. Interpretation of prose beyond these checks still needs human review.

## Actual agent runs

The initial adapter supports Linux and Codex CLI 0.155.1, with an existing host login. Other versions and hosts are unvalidated and fail closed. Revalidate isolation and the event contract before changing the supported version. Python's standard library is sufficient for the harness itself.

```bash
python3 -B evals/workflows/run.py --live \
  --case capture-failure --case preserve-user-work --case missing-sibling \
  --limit 3 --timeout 120
```

The command makes at most three agent invocations, each limited to 120 seconds. There are no automatic retries. The CLI chooses its default model with user configuration disabled; the runner does not change the user's saved model. Runs consume existing account usage. The timeout and invocation limit are bounds, not a dollar budget.

The agent uses the copied skill and its real bundled helpers. Fixtures cover capture success and failure, unavailable runtime, stale evidence, staged user work, tracker arguments, untrusted report text, and an absent optional sibling. Evidence cases intentionally request only capture, and the handoff case starts at an already resolved route. These are focused workflow scenarios, not complete PR publication or whole-board tests.

## Isolation

The trusted host CLI retains authentication for model traffic. Agent command environments are separately scrubbed; fixture HOME and Git configuration contain no user credentials. The named permission profile denies reads outside the workspace and required runtime files, makes the installed skill and tool doubles read-only, and denies command networking. Browser tools, MCP servers, plugins, hooks, and other host integrations are disabled. The run has no Git remote configured for publishing.

Before each invocation, the runner executes an isolation probe through the same host permission profile: fixture writes must work, reading an outside canary and modifying the skill must fail, and network connection must fail. A missing or unsupported sandbox stops execution. These controls use the documented [Codex permission profiles](https://developers.openai.com/codex/permissions), verified with the installed CLI. Model service traffic is separate from command networking.

The fixture is writable so the agent can perform real Git operations. Assertions check command results and final state; they are regression checks, not a security proof against an agent trying to forge every observation. No live tracker, publication, or browser capability is under test.

## Results and regrading

Runs go into a new ignored `evals/results/workflows-*` directory. Each case retains its request, skill payload hashes, starting repository state, host version, event stream, process result, structured response, final diff, and judgment. Recorded usage comes from the host's turn events. The host event stream may omit the resolved model identity; the report then records only the requested host default, without inventing a model name.

A setup failure, agent failure, timeout, grading failure, and completed failing scenario are distinct. Exit 0 requires all selected scenarios to pass. A successful process exit alone never establishes a successful workflow.

After fixing a grader, preserve the agent run and create a separate offline judgment:

```bash
python3 -B evals/workflows/run.py --regrade evals/results/workflows-RUN
```

Each regrade gets a unique JSON file with the grader hash and previous pass state. It invokes no agent and leaves the original result untouched. Keep cases from one underlying scenario together when building future held-out evaluation sets. Repeat live runs deliberately when measuring variability; retain every attempt.

See `findings.md` for measured pilot outcomes and limits.
