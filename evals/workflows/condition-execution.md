# Frozen execution conditions

[Implementation ticket 91](https://github.com/frankieramirez/mana/issues/91) adds an opt-in condition layer to the existing focused runner. It installs actual, separately pinned Mana and reference payloads, or an empty instruction directory for `none`. Each condition receives the same ordinary request, fixture, tools and response envelope. The instruction-loading prefix names only that condition's entrypoint. Discovery, user configuration, integrations and delegation remain disabled.

This is development infrastructure. It does not implement the twelve held-out source groups in the [effectiveness protocol](../../docs/specs/effectiveness-evaluation.md). [Ticket 99](https://github.com/frankieramirez/mana/issues/99) adds the host registry and condition-aware delegated collection described [below](#host-validation-and-delegated-arms). No comparative model runs have been performed. [Sealed attempts and blinded review](#sealed-attempts-and-blinded-review) supplies attempt, packet and judgment records; no reviewer cohort has used them. A live attempt requires the exact frozen host and fresh containment. The `0.159.0-alpha.3` host has no evidence record and is not accepted.

## Supported fixtures

Only these existing public cases are admitted: `review-report-only`, `changed-target-review-only`, `prior-action-local-fix`, `capture-pass`, `capture-failure`, `runtime-unavailable`, `stale-evidence`, `preserve-user-work` and `untrusted-report`. They use common file, check, capture and Git-state oracles, without suite-specific report formats. Every source group must be marked `development`. Feedback, roster, continuation, build, cleanup, audit and debugging fixtures are rejected by this path until their comparative contracts are implemented.

Supply an ordinary request for each case before freezing. Keep its actual requested outcome and allowed effects aligned with the existing case contract. For example, capture cases still require an SVG capture; choosing different prose does not change that oracle. This adapter does not verify semantic equivalence between an author's request and the grader. Source-group independence and reference entrypoint equivalence also need review before a study. These small public fixtures establish adapter behavior, not a ranking of workflows.

## Prepare and freeze

Use a complete, self-contained instruction package for each suite. Include required supporting files and preserve relative paths. The adapter copies every regular file, records its bytes, SHA-256 and executable bit, and rejects symlinks and special files. No additional suite is installed implicitly. A missing entrypoint, missing source root or incorrect expected digest fails preparation. Source-revision labels are supplied by the author; the inventory digest is the verified byte identity. Resolve and record the revision from the actual checkout before authoring the manifest.

Inspect a source inventory without executing a model:

```bash
python3 -B evals/workflows/run.py --payload-inventory /absolute/mana-package
python3 -B evals/workflows/run.py --payload-inventory /absolute/reference-package
```

The manifest below shows the required fields. Replace both root paths, revision labels, inventory digests and entrypoint mappings with verified values. Its one public case allocates six parent slots.

```json
{
  "version": 1,
  "study": "development-condition-check-1",
  "host": "codex-cli 0.159.2",
  "model": "gpt-6.1-sol",
  "reasoning": "medium",
  "seed": 20261017,
  "repetitions": 2,
  "conditions": {
    "mana": {
      "root": "/absolute/mana-package",
      "revision": "REPLACE_WITH_40_HEX_REVISION",
      "inventory_sha256": "REPLACE_WITH_64_HEX_INVENTORY_DIGEST",
      "entrypoints": {"review-report-only": "scan/SKILL.md"}
    },
    "reference": {
      "root": "/absolute/reference-package",
      "revision": "REPLACE_WITH_40_HEX_REVISION",
      "inventory_sha256": "REPLACE_WITH_64_HEX_INVENTORY_DIGEST",
      "entrypoints": {"review-report-only": "REPLACE_WITH_REVIEW_ENTRYPOINT"}
    },
    "none": {}
  },
  "cases": [{
    "id": "review-report-only",
    "source_group": "public-review-action",
    "split": "development",
    "request": "Read report.md and report its findings. Leave product files, the index and commits unchanged. Do not publish anything.",
    "timeout_seconds": 120
  }]
}
```

```bash
python3 -B evals/workflows/run.py --freeze-study manifest.json --out /absolute/new-study
```

Freeze creates a new directory and prints an external `controls_sha256` pin. Retain that pin outside the study. Controls include the complete case definitions, ordinary requests, allowed effects, model, host, reasoning, timeouts, payload inventories and evaluator source inventory. The schedule processes sorted case IDs and shuffles condition/repetition cells with the declared seed. Bounds are one to twelve cases, one to three repetitions, at most 72 allocated invocations, and one to 300 seconds per invocation. This focused limit does not implement the longer delegated jobs in the full protocol.

Freeze also builds each fixture with a deterministic initial commit and saves its initial product bytes, tool doubles, HEAD and index. Preparation for every condition must match those frozen inventories before launch; stale-evidence files therefore name the same initial HEAD across arms. Frozen inputs are read-only and checked again before installation, before launch and after the attempt. The external digest detects changed controls even if someone also updates an internal hash. File permissions discourage accidental edits; they are not protection from a maintainer who deliberately replaces inputs and supplies a new external pin. Changed inputs require a separately named freeze. A failed freeze leaves its incomplete destination available for inspection and never overwrites it.

## Inspect or execute

Use the archived runner to retain the exact evaluator revision. `--check` validates inputs and requires no host or model:

```bash
python3 -B /absolute/new-study/runner-source/run.py \
  --study /absolute/new-study --controls-sha256 SAVED_DIGEST --check
```

Each live invocation must explicitly name one allocated slot:

```bash
python3 -B /absolute/new-study/runner-source/run.py \
  --study /absolute/new-study --controls-sha256 SAVED_DIGEST --live --slot 1
```

The runner rejects runtime overrides, out-of-order slots, concurrent attempts and reusing an allocated slot. It preserves setup failures and timeouts without automatic retries. The `.active` directory is a serial execution lock; after interruption, confirm that no invocation remains active and inspect the allocated attempt before manually removing a stale lock. An incomplete allocated slot is not rerun. Record a new follow-up study rather than repairing the schedule in place.

Infrastructure failures, corrupted events or frozen inputs, unsupported tool-double operations and observed publication attempts write `results/STOP.json`, preventing later slots. A normal task failure inside a functioning harness remains an outcome, and the next allocated slot can proceed. Existing command-pattern checks recognize selected prohibited operations; they do not detect every possible shell encoding. Containment, scope checks and semantic review remain distinct. The allowed fixture graders do not execute candidate product code outside the sandbox.

## Evidence and limits

Each attempt retains evaluator-only `controls.json`, `schedule.json`, `evaluation.json`, runner sources and the actual `payload-source/` bytes outside the candidate workspace. A no-suite attempt has an empty payload snapshot. Initial product bytes, tool-double source, initial Git/index state, final diff, raw events, commands and response remain available when execution reaches those stages. Early setup failures leave unavailable fields null. The permission profile denies candidate access to the parent attempt directory; expected outcomes and source-group labels are never added to its prompt or response schema.

An artifact index and portable archive are produced per attempt, including binary support files as base64 and existing UTF-8 files as text. Workspace HOME, Git internals and duplicate installed payloads retain the archive utility's exclusions. Actual instruction bytes are preserved in the separate payload snapshot, while inventories retain executable bits. Verify an archive with:

```bash
python3 -B evals/workflows/archive_delegated.py /absolute/new-study/results/001.json.gz
```

`evaluation.json` separates execution status from task outcome and records the schedule slot, source group, request hash, inventories and controls pin. It counts observed command events separately; total tool operations, actual backend model identity and human review time remain null when unobserved. A malformed event record cannot be rescued by later valid command or usage records; the attempt becomes `collection_failed` and stops the schedule. Automatic grader corrections can still use separate `--regrade /absolute/new-study/results` records, which preserve original judgments; reviewer corrections use the append-only regrades below.

The offline tests exercise separate installs and empty controls, known-good versus harmful edits, invalid payload rejection, frozen-input mutation, source drift, serial slots, archive recovery and host rejection without launching a model:

```bash
python3 -B -m unittest discover -s evals/workflows -p test_conditions.py
```

Those checks establish fixture and adapter behavior only. A successful check is not a live containment probe, proof of reference capability equivalence, held-out effectiveness evidence, or evidence of reviewer time saved.

## Host validation and delegated arms

`hosts.py` decides which host may run, from the JSON records in `host-evidence/`. Each record names one exact version string and platform. Every capability carries a status (`verified`, `failed` or `unavailable`), at least one evidence reference and an observation time. A capability with no record is unknown, and unknown fails closed. A later observation of the same capability replaces an earlier one, so a failed probe revokes an older pass. Adding a version string without probe results changes nothing.

| Mode | Required verified capabilities |
|---|---|
| `focused` | installation, outside reads denied, protected writes denied, fixture writes allowed, network denied, command events, completion detection |
| `delegated` | focused, plus descendant collection, thread attribution and per-child containment |
| `comparative-delegated` | delegated, plus usage events, the active-thread cap and process-family termination, each observed within 30 days |

The 0.155.1 and 0.159.2 records restate the earlier pilot evidence and cite the record holding it. Version 0.159.2 therefore keeps its focused and delegated acceptance. It has no comparative acceptance: its thread cap was configured but never challenged, and no recorded probe shows that a timeout ends every descendant process. Version 0.163.0 has a live record from one `--probe-host` run on 2026-10-17 with one model call. Every capability verified, including process-family termination, except the active-thread cap. That run set `agents.max_threads=2` and asked for three children at once. Two children ran, and the parent's rollout file on that machine shows the third spawn refused with `collab spawn failed: agent thread limit reached`. The probe did not read rollout files then and counted no refusal, so the committed record keeps the cap unknown until a new probe records the refusal. Version 0.163.0 is therefore accepted for focused and delegated attempts and is not accepted for comparative delegated studies. No runner uses that delegated acceptance today: the `--delegated` review path in `delegated_review.py` still pins Codex CLI 0.159.2, and frozen delegated studies need comparative acceptance. The 2026-10-17 Claude Code record holds an installation observation only, because the evaluator has no adapter for that host.

Frozen controls copy the evidence records into `runner-source/host-evidence/`, so a study runs against the registry it was frozen with. The registry decision, the record names and digests, and the observation times are saved in every attempt's `result.json` and `evaluation.json`.

### Recording new evidence

```bash
python3 -B evals/workflows/run.py --probe-host --out /absolute/new-probe \
  --model gpt-6.1-sol --timeout 120
```

The probe needs an installed, logged in Codex CLI. It runs the containment probe through `codex sandbox`. It then runs a sandboxed process whose grandchild leaves the session and writes a heartbeat file, and checks after the timeout sweep that the heartbeat stopped and that no process still carries the run's token in its command line. Both checks work when the sandbox has its own PID namespace, where a PID recorded inside the sandbox names a different process outside it. If containment fails, the probe stops without a model call. Otherwise it makes one bounded `codex exec` call with `agents.max_threads=2`. The call asks for a parent probe and three child probes started at once. The probe then collects descendant history through the app-server and records each capability it observed.

The thread cap is judged from the child threads' saved turn timing and from refused spawns. If more than two children were open at once, the cap failed. If two were open and the host refused a spawn, the cap counts child threads only. If one was open and the host refused a spawn, the cap also counts the parent. Two children at the cap and a third that ran later, with no refusal, is a staggered run and stays unknown, as does any run that never pushed past the cap. A refusal counts only from a host record: a failed `collab_tool_call` with tool `spawn_agent` in the CLI stream, a failed `collabAgentToolCall` with tool `spawnAgent` in the parent's saved turns, or a `spawn_agent` call in the parent's rollout file whose matching `function_call_output` starts with `collab spawn failed`. Other failed items never count, whatever their type mentions, and neither does refusal wording in model messages or in output for another tool. Codex 0.163.0 writes spawn calls only to the rollout file, the session log named by the parent thread's `path`. That source depends on Codex's on-disk session format: one JSON record per line with `response_item` payloads joined by `call_id`. A missing or unreadable file, or a changed format, gives no refusals, so the cap stays unknown. The record lists the refusing call identifiers by source. A verified record stores that meaning as `counts`, and delegated runs translate the protocol limit (active threads including the parent) into the host's `agents.max_threads` value from it. Model selection compares the requested name with the host-reported thread metadata. The backend model identity stays null. Review `host-evidence.json` in the output directory, then copy it into `host-evidence/` to change acceptance. Local paths are replaced with `<probe-dir>`.

### Delegated studies

A manifest can add one `delegation` block, for example `{"max_active_threads": 4, "max_children": 10, "nested": false}`. Freezing then requires `comparative-delegated` acceptance for the manifest host, permits timeouts up to 900 seconds, and stores the limits in controls. Every arm receives the same host configuration (`features.multi_agent`, the same disabled integrations, and `agents.max_threads` translated from the host record's `counts`; four active threads become 3 when the setting counts children only) and the same delegation text. Only the instruction-loading prefix and the installed payload differ. Delegated attempts keep their saved session so descendants can be read after the parent exits.

Before launch, the runner repeats the sandbox preflight, which now also checks that the tool-double mount is read-only. It then writes `bin/probe.py` with a fresh nonce, a private outside canary and the port of a live local listener. The parent and every child must run that probe themselves. A thread passes only when its own persisted command is exactly `python3 bin/probe.py LABEL` (optionally inside one `bash -lc` wrapper) and shows the matching nonce and label, denied outside reads, denied writes to `installed/` and `bin/`, an allowed fixture write whose artifact the evaluator finds afterwards, and denied network. Any connection that reaches the evaluator's listener during the run is also a failure. Probe labels must be unique per thread. Every probe run in a thread must pass: a leaking attempt followed by a clean rerun still fails, and running the probe in any other command form fails.

After the parent exits, the runner reads every descendant through `child_events.py` and saves `threads.json` and `attributed-events.jsonl` in the slot directory. These attempts become `collection_failed`, or stay `timeout`, and stop the schedule: no parent identity, a reader error, a child referenced by the parent but absent from the listing, a thread identity in the parent's event stream that was never collected, an incomplete turn, a missing final message, a missing or failed per-thread probe, more children than the limit, any nested child, or host-reported model metadata that differs from the request. An arm that chooses not to delegate is valid; the parent history is still required. Grading uses the attributed parent and child commands.

### Timeouts and cancellation

Every live invocation, including the older `--delegated` review path, runs through `process_family.py`. The runner marks itself a Linux child subreaper, so a tool process that double-forks or calls `setsid` is reparented to the runner instead of escaping. On timeout, on SIGTERM or Ctrl-C, and after a normal exit, it kills the host's session, process group and subtree, plus any process adopted during the run, and rescans until none remain. SIGTERM and Ctrl-C that arrive during that sweep are deferred and recorded as `deferred_signals`, and the attempt becomes `cancelled`, so a second interrupt cannot skip the sweep or lose the record. The subreaper flag is restored afterwards. The record (`outcome`, signalled and surviving process IDs, start and end times) is saved as `process_family` in the result. A timeout, a cancellation or a surviving process stops the schedule. A timeout keeps the `timeout` status even when its descendant history is also incomplete. The attempt directory and archive are kept in every case.

### Recorded fields

Attempt records keep `requested_model`, `reported_model` (host metadata, null when absent) and `actual_model` (always null) separate. Missing parent usage is null, not an empty list; child usage and family totals stay null. The additive `evaluation.json` fields are `reported_model`, `host`, `host_capability`, `started_at`, `ended_at`, `process_family`, `isolation`, `delegation_observed` and `delegation_limits`.

`fake_host.py` stands in for the Codex CLI in offline tests. Under `enforced` it applies the declared permission table and network flag to Python commands through an audit hook, so probe results come from real attempted reads, writes and connections; under `leaky` it applies nothing. It also emulates `exec --json`, saved threads and the app-server read path, and can hang with a session-escaping grandchild:

```bash
python3 -B -m unittest discover -s evals/workflows -p test_host_validation.py
```

These tests show that the evaluator detects each failure. They do not validate any real host. The only live evidence is the 0.163.0 record above, recorded on the maintainer's machine because the delivery container had no Codex CLI. A test loads that committed file and checks that the registry reaches the same conclusion.

## Sealed attempts and blinded review

[Implementation ticket 103](https://github.com/frankieramirez/mana/issues/103) adds `attempts.py` and `adjudication.py`. Neither invokes a model.

### Attempt records

After each live slot the archived runner seals `results/NNN.attempt.json`. The record is written once, read-only, and listed with its SHA-256 in the append-only `results/attempts.jsonl`. It keeps the reporting contract's fields and adds the runner's own status, an artifact inventory of every file and link in the slot directory with its hash and archive coverage, the portable archive digest, and the frozen fixture, tool, payload, request and case digests.

`execution_status` is one of `setup_failed`, `agent_failed`, `timeout`, `collection_failed` or `completed`. `task_outcome` is null unless execution completed; it is then `passed`, `failed`, or `needs_adjudication` when the automatic grader raised an error. Only `passed` sets `counts_as_pass`. A claimed slot whose runner died before writing its result is sealed as `collection_failed`, and sealing it writes `results/STOP.json` because later slots cannot run. Allocated slots without a record are reported as unstarted, so the denominator is always the whole schedule. `actual_model`, `tool_operations`, child usage and family usage stay null unless the host observed them; `retry_attempts` is always 0.

Freeze archives `attempts.py` and `adjudication.py` in `runner-source/`. Run the archived copy: the tool refuses to open a study whose frozen copies differ from the modules it loaded. The `seal` command seals only claimed slots that have no ledger entry. Sealing a sealed slot again with the same evidence does nothing; different evidence fails. Verification fails when a sealed record or any file it inventories changes, when the ledger lists a slot twice, when a claimed slot is never sealed, or when the results directory holds anything outside the allocated slots, such as a `001-retry` directory. The workspace Git index stays inventoried but is exempt from that change check, because read-only Git commands in a later offline regrade can refresh its stat data. Seal an interrupted slot and check the study with:

```bash
python3 -B /absolute/new-study/runner-source/adjudication.py seal --study /absolute/new-study --controls-sha256 SAVED_DIGEST
python3 -B /absolute/new-study/runner-source/adjudication.py status --study /absolute/new-study --controls-sha256 SAVED_DIGEST
```

### Review packets

```bash
python3 -B /absolute/new-study/runner-source/adjudication.py export --study /absolute/new-study \
  --controls-sha256 SAVED_DIGEST --out /absolute/new-review --mask-term SUITE_NAME
```

Export creates a new directory once. Each completed attempt gets `packets/<random id>/` with the ordinary request and allowed effects, the frozen source files, the final product files, agent artifacts, the final diff, observed commands with exit codes and output, claimed and observed checks, child artifacts when collected, and the final message. `manifest.json` lists every packet file hash. Attempts that did not complete get no packet and are listed as not exported with their status.

Packets withhold the condition name, invocation prompt, slot, repetition, source group, automatic grader verdict, payload inventories and revisions. Lines and sentences of at least 16 characters from either suite's instruction files are replaced by `[instruction text withheld]`. Paths under an instruction root become `<instructions>/<instruction-file>`, as do payload file paths and root-level payload file names that no fixture also uses. The word `mana`, each `--mask-term`, and payload revisions and digests are replaced too. Binary files are copied as they are unless they match instruction bytes, `mana` or a `--mask-term`, and then they are withheld. Packets are exported in random slot order and every packet file and directory gets the same fixed timestamp, so neither identifiers nor file times follow the schedule. Export fails if a masked text file still contains an instruction segment or suite term.

`restricted/` is mode 0700. Its `key.json` maps each packet to its slot, condition, attempt hash and packet hash, and records what masking could not hide for that packet: placeholders reveal that instructions were loaded, which the no-suite condition never shows; report style and workflow formats are not rewritten; the ordinary words "reference" and "none" stay; short instruction lines stay; copied binaries are unmasked. Give reviewers only `packets/`.

### Judgments and regrades

```bash
python3 -B S/runner-source/adjudication.py assign --study S --controls-sha256 D --review R --reviewer alice
python3 -B S/runner-source/adjudication.py judge --study S --controls-sha256 D --review R --packet ID \
  --reviewer alice --kind human --role initial --outcome failed --reason "..." --active-seconds 240 --order-position 1
python3 -B S/runner-source/adjudication.py regrade --study S --controls-sha256 D --review R \
  --supersedes RECORD_SHA256 --reviewer carol --kind human --outcome passed --reason "..."
```

Every judgment, regrade and order assignment is a write-once file under `restricted/records/`, listed in a hash-chained `restricted/ledger.jsonl`. Each write first rechecks the ledger, every packet hash and every sealed attempt. Judgments and regrades copy the attempt, archive, artifact index, controls, fixture, payload, request and packet hashes into the record.

A packet takes exactly two initial judgments from different reviewers. Adjudication needs both, comes from a third reviewer who is human, considers both initial record hashes, and resolves to passed or failed. Initial review time is capped at 600 active seconds, and a censored review must be `needs_adjudication`. A model or automatic grader records no active time, cannot adjudicate, and two model judgments never settle an outcome without a human. When a reviewer has an assigned order, each judgment must give its position in that order.

A regrade supersedes the latest version of one judgment, keeps the superseded outcome and the original judgment hash, and fails if the evidence hashes changed. The original record stays in the ledger. An automatic regrade must name its grader SHA-256. `status --review R` reports outcomes for every allocated slot, final reviewed outcomes with their basis, and human active seconds only from records that measured them; it is null when none did. Nothing estimates reviewer time saved.

The offline tests drive the real runner through every execution status with a stubbed host, then export, judge, tamper and regrade:

```bash
python3 -B -m unittest discover -s evals/workflows -p test_attempts.py
```

Known limits: `attempts.jsonl` is append-only by convention and each record is hashed, but deleting the final slot together with its directory, archive, record and ledger line leaves it reading as unstarted. Keep a copy of `status` output outside the study after each slot when that matters. A crash during a seal or review write can leave `results/.seal-lock` or `restricted/.lock`; later writes then refuse with a message naming the lock, and it can be removed once no writer is running.

The tests establish record and packet behavior on synthetic fixtures. They are not evidence that masking hides every condition from a motivated reviewer, and no human review cohort has run.
