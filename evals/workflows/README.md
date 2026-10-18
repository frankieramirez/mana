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

The adapter supports Linux and an existing Codex CLI login. It accepts exactly the versions whose committed evidence records in `host-evidence/` verify the capabilities a mode needs, as read by `hosts.py`; see [host validation](condition-execution.md#host-validation-and-delegated-arms). The first records restate the 0.155.1 pilot and the 0.159.2 package C probe. The 0.163.0 record comes from a live `--probe-host` run and supports focused and delegated attempts; its thread cap stays unknown, so it does not support comparative delegated studies. No runner uses that delegated acceptance today: the `--delegated` review path in `delegated_review.py` still pins Codex CLI 0.159.2, and frozen delegated studies need comparative acceptance. Versions without a record are unvalidated and fail closed. Revalidate isolation and the event contract with `--probe-host` before adding a record. Python's standard library is sufficient for the harness itself.

```bash
python3 -B evals/workflows/run.py --live \
  --case capture-failure --case preserve-user-work --case missing-sibling \
  --limit 3 --timeout 120
```

The command makes at most three agent invocations, each limited to 120 seconds. There are no automatic retries. The CLI chooses its default model with user configuration disabled unless `--model` is supplied. `--reasoning` defaults to `medium`. The runner records both settings without changing the user's saved configuration. Runs consume existing account usage. The timeout and invocation limit are bounds, not a dollar budget.

The agent uses the copied skill and its real bundled helpers. Fixtures cover capture success and failure, unavailable runtime, stale evidence, staged user work, tracker arguments, untrusted report text, and an absent optional sibling. Evidence cases intentionally request only capture, and the handoff case starts at an already resolved route. These are focused workflow scenarios, not complete PR publication or whole-board tests.

Four additional scenarios cover the authority and recovery changes:

| Case | Stage and observable outcome |
|------|------------------------------|
| `prior-action-local-fix` | Completed review at Stage 6. Apply the already chosen local fix and verify it, preserving HEAD and the index. |
| `review-report-only` | Completed review at Stage 6. Report findings while preserving product files, HEAD, and the index. Reject observed publication attempts even when they fail. |
| `changed-target-review-only` | Completed review at Stage 6 after approval limited to a different repository and PR. Report the current findings without transferring that permission, preserving product files, HEAD, and the index. |
| `repair-push-rejected` | Repair publication stage. Commit the supplied repair, observe a real non-fast-forward rejection from a disposable local remote, and preserve both the repair commit and concurrent remote commit. |

Live evaluation of the changed-target scenario has not run. Its offline scope checks establish fixture and grader behavior only.

Four cleanup scenarios use `cleanup_fixtures.py` at standalone cleanup's validation stage. `cleanup-validation-failed` supplies a rename with a real `NameError`; `cleanup-validation-passed` checks the corrected function against populated and empty inputs. `cleanup-validation-blocked` reports a missing runtime with exit 127. `cleanup-validation-reused` records a successful check during fixture setup and supplies its source hashes for a no-edit continuation. The grader compares check reports with command outcomes and final repository state, rejects masked command exits, and preserves the starting index. These cases do not exercise reviewer dispatch or measure comment-retention judgment.

```bash
python3 -B -m unittest discover -s evals/workflows -p test_cleanup.py
```

The tests execute fixture checks and supply synthetic agent records to establish grader behavior. Live cleanup runs have not been performed. On a validated host, use `--live --case cleanup-validation-failed --case cleanup-validation-passed --case cleanup-validation-blocked --case cleanup-validation-reused --limit 4 --timeout 180` for the bounded agent trial. A final narrative that contradicts its structured check records still needs semantic review.

## Focused debugging cases

`debugging_fixtures.py` exercises the stage-loaded debugging procedure through five bounded synthetic cases. Four use the local implementation stage; the missing-runtime case uses triage and permits no production edits.

| Case | Observable acceptance |
|------|-----------------------|
| `debugging-boundary` | Normalize an omitted optional name at input while preserving supplied and empty names. |
| `debugging-producer` | A failed settlement propagates its error without leaving a partial payment; the successful case records both entries. Both paths preserve prior transactions. A silent fallback or clearing earlier records fails. |
| `debugging-disproved` | Observe raw and cached timestamps, remove a supplied speculative timezone edit, and repair cache invalidation while preserving same-file user configuration, staged notes, and untracked work. |
| `debugging-blocked` | The synthetic browser prerequisite exits before any scenario executes. Passing neighboring unit checks cannot verify the original browser claim. |
| `debugging-drift` | A fixture actor changes the source during reproduction. Report stale evidence, or rerun and report the subsequent stable source. |

The fixture's original path is `bash check.sh symptom`; its neighboring contract is `bash check.sh neighbors`. The timestamp case also exposes `bash check.sh experiment`. Each command emits observed source hashes with its actual result. The grader requires a failing original reproduction before repair, a recheck at the final source, and a valid neighboring case. It rejects masked commands and retains the original repository/index scope checks. The fixture-controlled source change is synthetic and does not measure concurrency coverage in a real application.

Independent final checks execute only inside a disposable copy under the same Codex permission profile, with a read-only candidate snapshot and networking denied. The current host must be validated and a fresh containment probe must pass before candidate code can run, including denied write attempts against each copied input. The saved candidate and evidence are never the recheck working directory. Missing sandbox support or failed preflight yields `independent debugging validation unavailable`, which cannot pass; a timed-out check is a recorded failure. Each command runs in its own process group, which is cleaned after timeout or leader exit; surviving descendants make the check fail. Offline regrading uses the same gate. The offline behavioral tests inject a runner for curated fixture implementations; separate isolation tests exercise the production fail-closed path, command construction, and real process-group cleanup. Those doubles do not establish live sandbox protection on an unsupported host.

```bash
python3 -B -m unittest discover -s evals/workflows -p test_debugging.py
python3 -B evals/workflows/run.py --live \
  --case debugging-boundary --case debugging-producer \
  --case debugging-disproved --case debugging-blocked --case debugging-drift \
  --limit 5 --timeout 240
```

The offline tests execute real fixture commands and grade synthetic event records. No debugging agent trials have run. These development cases establish fixture and grader behavior; they do not establish an improvement over a baseline or evaluate full triage, publication, intermittent failures, or investigation-budget decisions. Keep unseen task variants separate for the effectiveness comparison.

The focused-case loader limits the added review skills to these stages. Delegation stays disabled for focused cases; these cases do not test finding quality, reviewer orchestration, or a full feedback cycle. Human review must also check that the agent did not ask again for an action already supplied and that its report accurately explains any recovery. The command-pattern checks detect selected prohibited attempts, not every possible shell encoding. Final repository state supplies the primary scope oracle.

## Isolation

The trusted host CLI retains authentication for model traffic. Agent command environments are separately scrubbed; fixture HOME and Git configuration contain no user credentials. The named permission profile denies reads outside the workspace and required runtime files, makes the installed skill and tool doubles read-only, and denies command networking. Browser tools, MCP servers, plugins, hooks, and other host integrations are disabled. Only the rejected-push fixture has a publishing remote: a disposable bare repository inside its own workspace. No remote service is reachable through it.

Before each invocation, the runner executes an isolation probe through the same host permission profile: fixture writes must work, reading an outside canary and modifying the skill must fail, and network connection must fail. A missing or unsupported sandbox stops execution. These controls use the documented [Codex permission profiles](https://developers.openai.com/codex/permissions), verified with the installed CLI. Model service traffic is separate from command networking.

The fixture is writable so the agent can perform real Git operations. Assertions check command results and final state; they are regression checks, not a security proof against an agent trying to forge every observation. No live tracker, publication, or browser capability is under test.

## Skill discovery, selection only

`discovery.py` measures whether a host picks the right skill from ordinary language, apart from how well the skill then runs. The contract is [discovery-and-hosts.md](../../docs/specs/discovery-and-hosts.md). The focused runner above names one skill path in its prompt and turns host discovery off, so none of its results say anything about discovery.

Each case installs the whole catalog under `.agents/skills/` in a disposable repository and records a snapshot of every entrypoint's name, description, explicit-only flag and folder digest. The installed bytes must match the source. The prompt is the user's request plus one sentence saying the files are synthetic, and it may not carry a workspace or catalog path. The host settings match the focused runner's except that `features.skip_host_skill_discovery` stays off. Delegation stays off. The product tree and Git are read-only and only `artifacts/` is writable, so a run ends before any product mutation. A containment probe checks this through the host sandbox before the model call, including a read attempt on `discovery-cases.json` that must be denied.

The host keeps the operator's environment, so it may also list skills from `~/.agents/skills`, `~/.codex/skills` or `/etc/codex/skills`. The evaluator never edits those folders, the host's configuration or its credentials. It records their listing in every result and probe record, and in a case run any `SKILL.md` reference outside the workspace catalog goes to `needs_adjudication`. Outside means an absolute path beyond the workspace, a `~` path or a `..` escape; a bare `SKILL.md` in a search names nothing. The probe records outside reads without letting them hide a direct canary read.

The catalog's `disable-model-invocation` is a Claude Code field. Codex names a skill explicitly with `$name` and reads its own implicit-invocation policy from `agents/openai.yaml`, so the catalog's explicit-only flags may mean nothing to Codex until the probe shows otherwise.

`discovery-cases.json` holds the 46 cases from the spec: one positive and one negative per skill and the eight overlap and capability cases, each with its accepted routes, accepted fallbacks and forbidden actions. The loader rejects an ordinary request that names a skill, an explicit-only skill expected from ordinary language, and a negative case that accepts its own skill. A changed explicit-only flag in the catalog stops every run until the routes are revised. A live run must pass the file's digest, so routes are locked before results.

The event stream is the evidence. A load counts only when a recorded command printed that entrypoint's description line and body; reading descriptions across several skills is a catalog scan. A load is `direct` only when one plain read names exactly that SKILL.md path, with no glob, search or pipe, and the folder name appeared in no earlier tool item: a command, a `file_change` or any other item with output. The model's own reasoning and replies do not count, because a randomly named folder can reach them only from the host's skill list or from a tool output that already counts. Every other load is `search`. Hard verdicts come only from unambiguous evidence, and the rest goes to `needs_adjudication` with the commands a person should read:

| Field | Values | Meaning |
|---|---|---|
| `activation` | `correct`, `missing`, `unnecessary`, `unobservable`, `needs_adjudication` | Loaded entrypoints against the accepted routes. Only an automatic skill or a skill the user named can be missing. |
| `routing` | `correct`, `fallback`, `wrong`, `unobservable`, `needs_adjudication` | The first loaded skill, or `ordinary`, against the accepted and fallback routes. |
| `execution` | `not_exercised`, `scope_violation`, `needs_adjudication`, `timeout`, `boundary_breach`, `collection_failed` | What happened after selection. Selection-only runs never claim a workflow outcome. |
| `capability_limit` | `none`, `declared` | The skills or capabilities the case removes, kept apart from routing so a correct route that hits one stays correct. |

`scope_violation` comes only from a forbidden write shown by a `file_change` event or by a failed redirect, `tee`, `touch`, `mkdir`, `rm`, `mv`, `cp`, `sed -i` or `apply_patch`. A product state change is a `boundary_breach`. When a case forbids an action and the run had any other failed command, execution is `needs_adjudication`. A successful read-only `git` call is ordinary inspection, a successful Git write shows up as a product state change, and the offline `gh` double always fails. Selection is `unobservable` when events are lost or the host has no verified `skill_discovery` record.

```bash
python3 -B evals/workflows/run.py --discovery-check
python3 -B -m unittest discover -s evals/workflows -p test_discovery.py
```

The check validates the routes against the catalog and prints their digest and the seeded 24-slot schedule for the first live group; no agent runs. The tests drive every judgment through `fake_host.py`, including its keyword selector over listed descriptions. That selector is an offline fixture. Fake runs are always labelled `offline-fixture` and refuse to run as live.

A live result needs a host record that verifies `skill_discovery`. No recorded host has one, so `--discover` refuses every version today. The activation probe installs two synthetic canary skills in randomly named folders, each holding a secret word. The explicit one carries both `disable-model-invocation: true` and `agents/openai.yaml` with `policy.allow_implicit_invocation: false`. The probe asks for both words without naming either:

```bash
python3 -B evals/workflows/run.py --probe-discovery --out evals/results/discovery-probe --model MODEL
```

It makes one model call, limited to 120 seconds, after the containment probe passes. `skill_discovery` is verified when the automatic canary is read directly. A secret that reaches the response while no command output held it records `unavailable`. Everything else stays unknown, including a run where the model never reads the automatic canary. `explicit_only_honored` fails on a direct or invisible load of the explicit canary, is verified when its secret appears nowhere beside a verified automatic load, and otherwise stays unknown. Review the record before copying it into `host-evidence/`. After that, one case runs with:

```bash
python3 -B evals/workflows/run.py --discover --live --case dispel-positive --routes-sha256 DIGEST --model MODEL
```

Each invocation is one serial parent with a 120-second limit, no children and no retries.

## Results and regrading

Runs go into a new ignored `evals/results/workflows-*` directory. Each case retains its request, skill payload hashes, starting repository state, host version, event stream, process result, structured response, final diff, and judgment. Recorded usage comes from the host's turn events. The host event stream may omit the resolved model identity; the report then records only the requested host default, without inventing a model name.

A setup failure, agent failure, timeout, grading failure, and completed failing scenario are distinct. Exit 0 requires all selected scenarios to pass. A successful process exit alone never establishes a successful workflow.

After fixing a grader, preserve the agent run and create a separate offline judgment:

```bash
python3 -B evals/workflows/run.py --regrade evals/results/workflows-RUN
```

Each regrade gets a unique JSON file with the grader hash and previous pass state. It invokes no agent and leaves the original result untouched. Keep cases from one underlying scenario together when building future held-out evaluation sets. Repeat live runs deliberately when measuring variability; retain every attempt.

See `findings.md` for measured pilot outcomes and limits.

## Package C focused comparisons

For explicit frozen Mana, reference and no-suite conditions, see [Frozen execution conditions](condition-execution.md). That opt-in path supports a declared subset of public development fixtures, installs distinct payloads, and preserves a hashed schedule. It does not replace the legacy commands below. The held-out study runs through the [complete comparative study](condition-execution.md#complete-comparative-study), which stays gated until every recorded gate opens. Each allocated slot is sealed as an immutable attempt record, and completed attempts export to blinded review packets with independent judgment and regrade records.

The first prose instruction ablation has its own frozen dispel payloads and adapter in [Prose instruction-ablation payloads](prose-ablation.md), and its six independent confirmation groups in [Prose-ablation confirmation cases](prose-confirmation.md).

Use `--skill-root /absolute/baseline/skills` to install a saved baseline payload; omit it for the candidate. Each run records the installed file hashes and retains the runner sources beside the results. Keep baseline and candidate requests, model, reasoning, and tool configuration identical. Example:

```bash
python3 -B evals/workflows/run.py --live \
  --case targeted-incorrect-suggestion --case full-feedback-judgment \
  --case small-risk-roster --case repair-push-rejected \
  --case targeted-supported-fix --limit 5 --timeout 240 \
  --model gpt-6.1-sol --reasoning medium \
  --skill-root /absolute/baseline/skills
```

The feedback fixtures exercise the real bundled helper against an offline `gh` double. Unknown GraphQL operations fail rather than returning unrelated synthetic data. `targeted-incorrect-suggestion` rejects a suggestion contradicted by a caller. `full-feedback-judgment` must also accept a demonstrated arithmetic defect and a useful spelling correction. Both are dry runs. `targeted-supported-fix` is a held-out one-thread repair through the supported no-subagent fallback: it must fix the arithmetic defect, preserve the negative-input guard, verify, and commit without pushing. `small-risk-roster` ends at Stage 3 and checks security/adversarial coverage plus both ticket requirements. It does not measure reviewer findings or independent validation.

`context.full_reads` counts complete Markdown/JSON file contents observed in command output, including repeat retrievals. Counts exclude mere filename mentions. `total_full_read_bytes` includes duplicates; `redundant_full_read_bytes` measures the repeated portion. `tool_output_bytes` is all observed command output. Partial or truncated reads are not reconstructed as full file reads. Inspect saved command events for those reads before interpreting a zero. These are observable context measures, not an exact reconstruction of the model's context window. Host input tokens are cumulative processing, including repeated conversation context. Actual model identity remains null when the host does not expose it.

The focused path continues to disable delegation. The opt-in `--delegated` extension is documented in [delegated-evaluation.md](delegated-evaluation.md), including child-history coverage and containment requirements. These focused stages and the repair fallback do not establish full multi-reviewer equivalence. Do not use a passing roster case to claim independent finding validation. The package C record in `docs/plans/frontier-workflows.md` distinguishes these limits from measured outcomes. The event-based approach follows [OpenAI's skill evaluation guidance](https://developers.openai.com/blog/eval-skills); host acceptance still requires an executed local containment and event check.


For delegated execution, use the separate offline inspection command. It preserves the original result and does not execute a model:

```bash
python3 -B evals/workflows/audit_delegated.py evals/results/delegated-review-RUN
```

Portable synthetic evidence archives include raw parent events, persisted family history, runner snapshots and review artifacts. Host HOME, Git internals and installed payload copies are excluded; payload hashes and source revisions identify the frozen inputs. Verify every archived file digest with:

```bash
python3 -B evals/workflows/archive_delegated.py evals/workflows/evidence/RUN.json.gz
```


## Package D named continuation

`portal_fixtures.py` extends the same runner with changing offline tracker/PR state and a real disposable Git remote. The build fixture has two independent ready members, an open dependent member, another owner, an unready member and unrelated ready work. The map fixture links a downstream build but authorizes only its decision destination. Only portal is installed, exercising the ordinary-task fallback. The workspace-stop case imposes a host isolation limit. Single-ticket and `go` cases retain one handoff. A resume fixture seeds a cancelled run with an actual unit commit, synthetic open PR and unfinished user edit; saved wider actions do not authorize current publication.

Run the deterministic suite without any model invocation:

```bash
python3 -B -m unittest discover -s evals/workflows -p test_portal_run.py
```

Live invocations require the explicit controls in `package-d-controls.json`. Keep every attempt and any separate offline regrade. Package D's plan record distinguishes the initial conflicting-validation fixture and permissive-grader result from the corrected observations. The grader requires observed successful unit checks and verified state; a commit alone cannot establish a completed unit. Tracker transport queries model the bundled helper shapes and reject unsupported operations, so these are bounded synthetic outcomes. Managed workspace APIs and real tracker/publication behavior remain unmeasured.


The portable package D record is [package-d-results.json](package-d-results.json). Its per-attempt archives retain raw events, synthetic workspaces/state, frozen runner sources and separate regrades. Verify an archive without invoking a model:

```bash
python3 -B evals/workflows/archive_delegated.py evals/workflows/evidence/package-d-RUN-CASE.json.gz
```

That existing archive tool supports these serial records as well as delegated evidence. Installed payload hashes identify each snapshot. The final validator output is in `evidence/package-d-validation.txt`.

## Build progress leftover evidence

`build_fixtures.py` adds the `build-parent` fixture for the **Leftover evidence** path in `build-progress.md`, which conjure owns and cast and scry copy. Its offline `gh` holds an open build parent, #40, whose body starts with `Work kind: build` and carries Destination, Build order, and Next step. Both members are closed. #41 closed when PR #51 merged. #42 closed when PR #52 merged, before any agent run existed, as `ultima#746` did. No PR is open. The one unmet Destination item is three recorded agent runs on one merged revision, which #42's Build order Outcome names. The tracker also holds the closed planning map #30 and an older, unrelated ready ticket #99, which a global `next` returns first.

| Case | Request | Observable outcome |
|------|---------|--------------------|
| `scry-build-leftover` | scry on 40, tracker writes authorized | `leftover-ticket` |
| `conjure-build-leftover` | conjure on 40, progress only, tracker writes authorized | `leftover-ticket` |
| `scry-build-leftover-read-only` | scry on 40, every tracker write forbidden | `leftover-report` |

`leftover-ticket` grades the final tracker state. It accepts either branch of the reference, and exactly one of them:

- #42 reopened with no assignee and the ready label, carrying a new comment with an `## Agent Brief` line that the call log shows was posted before the reopen.
- One new open, unclaimed member with `Build parent:` and `Planning source:` lines, an `## Agent Brief`, the category and ready labels, native attachment under #40, and an entry in the parent's Build order.

Both branches together count as ticketing one item twice, and neither counts as leaving the evidence without a ticket. In either branch the parent stays open, keeps its marker, Destination, and original Build order entries, and gets no Completion comment. No other ticket changes state, labels, or assignees, and the report contains `Implement <ticket URL>, following its brief.` for that ticket, never #99.

`leftover-report` requires the tracker to match its starting state and the call log to hold no write, including a failed one. The report must contain `Check progress and close out the build effort at <parent URL>, reopening or filing tickets for its unmet evidence.` and list the actions it did not take: reopening #42 on one line, the agent brief, and the ready label, or the filing equivalents.

Every case must enumerate the members through a sub-issue read. A `gh` write in the agent's own command fails as bypassing `tickets.sh`, and a pull request or push fails as unrequested publication. The double answers the jq expressions the bundled `tickets.sh` and `map.sh` use, plain path expressions, and `--json` without `--jq`, plus PR and closing-reference reads. Any other operation exits 97 with a hint to rerun with `--json` alone.

The grader tests build each known good and bad outcome with the installed skill's real `tickets.sh`, so they also check that the double serves every call the reference makes:

```bash
python3 -B -m unittest discover -s evals/workflows -p test_build_leftover.py
```

Live evaluation of these cases has not run. The offline tests establish fixture and grader behavior only. A live run uses the usual controls:

```bash
python3 -B evals/workflows/run.py --live \
  --case scry-build-leftover --case conjure-build-leftover \
  --case scry-build-leftover-read-only --limit 3 --timeout 300
```


## Ultima follow-up authority

Four focused cases start from a completed audit with its existing report and one eligible candidate. `ultima-report-only` and `ultima-changed-target` require report delivery without changing the project. `ultima-local-fix` requires the already selected edit and successful verification while preserving HEAD and the index. `ultima-host-question` leaves the action unresolved on a host without a permitted question tool, so the report precedes an ordinary-text choice. None authorizes publication.

`ultima_fixtures.py` checks assistant report-link events, their ordering against observed shell edits or native patch events, unnecessary repeat questions in these bounded prompts, unsupported question calls, and attempted writes. The shared grader checks actual file contents, validation events, HEAD and the index. These checks use known fixture language and supported host event shapes; they do not establish a general semantic detector for every question or arbitrary write mechanism.

The synthetic grader tests cover both accepted and rejected outcomes:

```bash
python3 -B -m unittest discover -s evals/workflows -p test_ultima_followup.py
```

No live agent execution of these cases is recorded. The tests establish fixture and grader behavior, while the instruction change still needs a supported-host live comparison before making reliability claims.
