# Delegated review evaluation

This extends the existing workflow runner. Installed skill payloads stay frozen. The focused package C record remains unchanged in `package-c-results.json`.

## Collection contract

The adapter runs saved `codex exec --json` sessions on CLI 0.159.2. Ephemeral sessions are unsuitable because the earlier child probe could not load its parent rollout. The CLI stream alone omits child commands. After execution, a read-only app-server client initializes the documented JSON-RPC connection, lists all descendants across active and archived listings, reads thread metadata, and pages every turn with `itemsView: full`.

The [official app-server documentation](https://learn.chatgpt.com/docs/app-server) describes descendant filters and paginated history. The installed host's generated experimental schema was also checked. These interfaces are experimental; other CLI versions remain rejected for delegated runs.

Every normalized command carries its thread and turn identity, command text, output and exit code. Raw persisted items and final messages remain in the evidence. Missing referenced children, broken ancestry, incomplete turns, missing exit outcomes, absent final messages and absent per-thread containment probes reject execution acceptance. Nullable output remains explicitly marked unavailable in normalized commands and unchanged in raw history. The first full baseline exposed this distinction: its parent CLI empty output matched nullable stored output. Child artifact-writing commands had recorded exits and final artifacts but nullable output; those bytes are not invented or counted. The original rejection and subsequent offline audit are both retained. Collection includes descendants at every depth. The offline audit rejects unexpected nesting, maps every selected role and the validator to distinct probe-bearing threads, and requires reviewer completion events before the first merge command. It also compares persisted parent commands with the CLI stream.

Malformed CLI event lines and invalid event shapes are recorded as failures while valid events remain available for usage extraction and parent lookup. If a parent identity survives, descendant collection and attribution still run after a timeout or damaged event. The raw stream remains unchanged and a damaged run cannot pass execution acceptance. A missing parent identity is reported explicitly.

A rejected spawn call can appear only as a host diagnostic. The primary candidate logged an invalid agent name, recovered, and completed every selected child. Its failed call arguments are unavailable. Such diagnostics stay in the archive and record; no missing arguments or extra child execution are invented.

The API's model and reasoning fields are host-reported metadata. They do not prove a resolved backend model identity. Child usage is unavailable in this read path. Usage from the parent CLI turn event is retained separately; the host does not expose a family usage breakdown, so it must not be called total family usage. Complete Markdown/JSON matches in command output are a lower bound on loaded instructions; partial reads and delegation prompt context can be omitted. Repeated matches can include rereads of staged prompt files. Counts are per command; multiple copies within one output are not separately counted. Command-output bytes are observed bytes, including truncation where the host truncated output.

## Containment and bounds

The existing permission profile denies outside reads, installed instruction and tool-double writes, and command networking. The trusted CLI retains login only for model traffic. Every run performs the existing shell preflight, then the parent and every child must run an immutable probe. That probe attempts an actual outside read, attempts writes to both protected mounts, and attempts a connection to a live local listener. It also writes an authorized artifact. Successful probes must appear in each agent's own persisted commands, with exit zero and the expected output. Parent claims about a child do not satisfy this gate.

Each full-review CLI invocation has a 900-second hard process-group timeout. `--limit 1` permits one parent invocation per command with no automatic retries. The prompt caps the family at ten children and three concurrently; the host configuration caps active threads at four including the parent. The ten-child total is an instruction bound checked after collection, not a hard host quota. An excess rejects the run. Every attempt is retained, including timeouts and infrastructure failures.

The initial containment pilot used one parent, one child and 180 seconds. The first review pair is capped at two parent invocations and twenty children combined. Any later group gets a separately recorded limit before execution.

## Cases and decisions

`delegated-grading.json` records the rubric before outcome inspection and remains outside agent-readable fixtures. The primary case checks separate role and tenant failures at one location plus a pagination defect. Misleading suggestions challenge caller inspection and scope preservation. The held-out case uses retry termination, error propagation and queue preservation. Its definitions were written before inspecting the primary findings, with no skill tuning.

Both cases use full standalone review, explicit ticket requirements, the skill's complete risk-based reviewer roster and a separate validator. The supplied `gh` is a narrow offline fixture. These cases do not establish live GitHub feedback delivery, late PR comments, actual publication, or all possible review workloads. Prior focused repair results remain separate evidence.

Execution acceptance means observable, contained execution with scope preserved. It is distinct from the manual finding/requirements judgment and paired equivalence decision. The runner deliberately leaves `equivalence_passed` false; a durable comparison record must supply that decision and its evidence.

## Run

Freeze `skills/` from package B commit `e1f8417865b778faf0cc61297375f18551fc1c27` and package C merge `06fdc89`. Then run each variant sequentially:

```bash
python3 -B evals/workflows/run.py --live --delegated \
  --case delegated-full-review --skill-root /absolute/frozen/skills \
  --model gpt-6.1-sol --reasoning medium --timeout 900 --limit 1
```

Use `delegated-heldout-review` for the held-out case. Every invocation saves the runner source before starting. Do not compare the saved runner with a later working copy and silently change its original judgment. Record any offline reinspection separately.
