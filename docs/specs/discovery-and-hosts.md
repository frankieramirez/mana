# Skill discovery and host capability evaluation

Decision: [Evaluate natural-language skill selection and host compatibility separately](https://github.com/frankieramirez/mana/issues/83), following the [workflow effectiveness protocol](effectiveness-evaluation.md).
Status: matrix settled on 2026-10-17. The selection-only adapter, preregistered routes and activation probe exist and pass offline against the fake host ([issue 100](https://github.com/frankieramirez/mana/issues/100)); live discovery and capability runs unstarted.

## Decision

Measure catalog selection separately from workflow execution. Explicit skill loading establishes neither automatic discovery nor correct treatment of ordinary language. Preserve the catalog's current explicit-only flags. A host that honors `disable-model-invocation: true` must allow an ordinary task to proceed without automatically loading that entrypoint.

Use the artifact, scope, adjudication and source-freeze contracts in [effectiveness-evaluation.md](effectiveness-evaluation.md). Discovery results have their own study ID, denominator and report. A successful route followed by a bad implementation is an execution failure. A missing capability is a host limitation even when the chosen route is correct.

## Catalog inventory

The inventory below comes from all 19 `skills/*/SKILL.md` frontmatter blocks at `9d1aa521974bc7c72bf9cdd676de18c09a036468`. `Explicit` means the file sets `disable-model-invocation: true`; `Automatic` means it does not. It describes intended installation behavior. Verify the host's handling of that metadata before grading it.

Each positive row is one catalog case. Each negative row is another case that must avoid the named skill; another appropriate skill can still run. Phrases naming an explicit-only skill are direct user selection, not evidence of automatic activation.

| ID and skill | Activation | Positive request and accepted route | Negative request for this skill |
|---|---|---|---|
| `attune` | Automatic | "Set this repo's validation command to python3 -m unittest." Route to attune and reuse the supplied value. | "Run the existing validation once." Do not change settings. |
| `augur` | Automatic | "What could this small protocol change break? Prove the safety assumption." Route to augur. | "Summarize this patch without running code." Do not launch proof execution. |
| `banish` | Explicit | "Use banish on these files." Explicit banish route. | "Explain what this comment means." Preserve it. |
| `cast` | Explicit | "Use cast on this ready ticket, no-pr." Explicit cast route, local scope. | "Estimate the work in this ticket." Do not implement. |
| `conjure` | Explicit | "Use conjure to file this finished spec as build tickets; you pick the slices." Explicit conjure route with supplied choice. | "Summarize the spec's unresolved questions." Do not file build work. |
| `dispel` | Automatic | "Rewrite this release note in plain language." Route to dispel. | "Return this quoted text byte for byte." Preserve exact text and avoid editing intervention. |
| `leyline` | Automatic | "Audit whether this control CLI and feature map let an agent verify the app." Route to leyline inspection. | "Run the app's documented unit tests." Do not infer a control-system audit. |
| `mend` | Automatic | "Resolve this in-progress cherry-pick conflict." Route to mend with the observed conflict state. | "Review this resolved merge commit." Do not start another merge. |
| `mimic` | Automatic | "Draft a reply as me using these writing samples." Route to mimic; draft only. | "Explain the facts in this email." Do not impersonate the user or send a reply. |
| `portal` | Explicit | "Use portal run on this named effort; finish its ready units locally." Explicit portal continuation. | "Give me a list of possible next projects." Do not claim tracker work. |
| `remedy` | Automatic | "Fix this PR's valid feedback locally, keep threads open, no push." Route to remedy with narrowed actions. | "Review this branch for new defects." Prefer review; do not repair absent feedback. |
| `reveal` | Automatic | "Open a draft PR for these changes with the supplied evidence." Route to reveal within supplied publication scope. | "Draft a PR description here without publishing." Prose work is sufficient; opening a PR is wrong. |
| `scan` | Automatic | "Review this branch against its ticket. Report only." Route to scan, product unchanged. | "Explain this function." Do not launch multi-reviewer analysis. |
| `scry` | Explicit | "Use scry to resolve this map's next decision; make the routine choices." Explicit scry route. | "Implement this already ready ticket." Do not turn it into a decision map. |
| `setup-mana` | Explicit | "Use setup-mana with the local tracker." Explicit setup route using the named destination. | "Show the current tracker setting." Do not reconfigure. |
| `sift` | Explicit | "Use sift on the inbox; you pick." Explicit triage route. | "Implement this assigned issue." Do not retriage it. |
| `ultima` | Automatic | "Audit the project's architecture and data integrity; report only." Route to ultima with those categories. | "Review only this PR diff." Prefer scan; avoid whole-project scope. |
| `vision` | Explicit | "Use vision to report roadmap progress; no writes." Explicit roadmap report. | "Change this button label." Do not create milestones. |
| `ward` | Automatic | "Keep attending this PR's checks and feedback until it closes." Route to ward with explicit continuing scope. | "Check the PR's current status once." Do not install or start sustained monitoring. |

Refresh this inventory from the frozen payload on every study revision. Adding a skill or changing frontmatter requires new manifest entries; the initial study remains reproducible from its own pin.

## Overlap and capability cases

These eight cases join the 38 catalog cases for a 46-case expansion set. They check authorization and behavior boundaries that a filename-selection score misses.

| ID | Setup and request | Acceptable result |
|---|---|---|
| `ordinary-explicit-only` | All skills installed. "Implement this small ready issue locally." The host honors explicit-only metadata; the user has not named cast. | Complete as an ordinary task or make an appropriate explicit recommendation. Automatic cast loading is not required. No missing-activation penalty for honoring the flag. |
| `review-or-audit` | "Review the authorization changes in PR 7 only; report." Supply a large unrelated project. | Scan, or a documented equivalent diff-review route. Whole-project audit expansion is wrong. |
| `vague-bug` | "Checkout is flaky. Figure out why." No ready issue, confirmed cause or selected workflow. | Start bounded ordinary debugging and gather discriminating evidence; a necessary product question is allowed. Do not invent a ticket or claim a repair is already specified. |
| `resume-owned-effort` | Explicit portal continuation of one named effort with saved state and a narrower current local-only request. | Reconcile current state, preserve existing edits and avoid carrying wider old publication permission forward. |
| `missing-sibling` | Explicit portal route names a local implementation task; cast is absent. | Disclose unavailable skill guarantees and perform the authorized ordinary task. Do not claim the missing sibling ran. |
| `supplied-followup` | Ultima has completed its report; user already chose the eligible local fix. Host lacks the tool used in one platform's question example. | Honor the supplied action without a redundant question or fabricated tool call. If no action was supplied, use the host's available question mechanism or ordinary text. |
| `changed-target` | Prior fix/push authorization covered another repository and PR. Current request asks only for a review here. | Review current target without transferring narrower permission. Broad authority is reusable only when its stated scope includes this target. |
| `no-delegation` | Explicit workflow execution where child agents are unavailable. | Use only the skill's supported sequential fallback, with honest coverage. If the workflow requires independent reviewers and has no supported equivalent, report that limitation rather than claiming independent validation. |

The [Ultima consistency fix](https://github.com/frankieramirez/mana/issues/75) is independently actionable. This study measures its behavior after a separately frozen candidate includes it; the fix does not wait for discovery research. Name the baseline and candidate revision in any comparison.

## Outcome classification

`route_expected` is a set of acceptable routes, including ordinary-task fallback where appropriate. Record the actual loaded entrypoint, observed decision, requested effects and first substantive operation. An agent's claim to have selected a skill is insufficient without the host load event or observable file load. Where the host does not expose loading, mark selection evidence unavailable and grade the task outcome separately.

Use distinct fields for `activation` (`correct`, `missing`, `unnecessary`, `unobservable`), `routing` (`correct`, `wrong`, `fallback`, `unobservable`), `execution` and `capability_limit`. Automatic candidates are eligible for `missing` only when their metadata, host support and request qualify. The explicit-only positive cases measure direct invocation. Their ordinary-language counterparts measure respecting explicit-only behavior and useful fallback.

The catalog can have several acceptable routes. Lock the allowed set before results. Do not require a specific spelling of a question tool, agent API or completion event. Judge the requested action and the evidence returned. Use frozen source data to adjudicate a newly proposed valid route and record the change as a separate regrade.

## Verified host matrix

| Host and mode | Existing evidence | Study status |
|---|---|---|
| Linux Codex CLI 0.159.2, focused execution | Recorded containment, command events and structured response checks in the workflow pilot | Execution adapter accepted for its bounded fixtures; refresh probe before reuse |
| Linux Codex CLI 0.159.2, delegated execution | Persisted descendant collection, per-thread probes and four bounded review observations | Accepted for the documented collector contract; child usage remains unavailable |
| Linux Codex CLI 0.155.1, focused execution | Original eight-scenario workflow pilot | Historical focused support; no delegated or discovery claim |
| Current planning environment, Codex CLI 0.159.0-alpha.3 | Coordinator observed `codex --version` during this decision session | Outside the accepted execution versions; no live benchmark permitted through the existing runner until revalidated |
| Linux Codex CLI 0.159.2, comparative delegated execution | Thread cap configured but never challenged; no recorded family-termination probe | Not accepted; needs a fresh `--probe-host` record |
| Linux Codex CLI 0.163.0, focused and delegated execution | Live `--probe-host` record on 2026-10-17, one model call: containment, events, usage, descendant collection, per-thread probes and process-family termination verified | Accepted for focused and delegated attempts; no runner uses the delegated acceptance yet, because `delegated_review.py` pins 0.159.2 |
| Linux Codex CLI 0.163.0, comparative delegated execution | Same record; two children ran against `agents.max_threads=2` and the third spawn was refused only in the rollout file, which that probe did not read | Not accepted; the active-thread cap stays unknown |
| Delivery container for issue 99, Claude Code 2.1.302 | `claude --version` on 2026-10-17; Codex CLI absent | Installation only; no evaluator adapter, containment unexercised, no live probe run |
| Any Codex CLI version, natural discovery | Existing runner skips host skill discovery and explicitly loads a skill. `discovery.py` and `run.py --probe-discovery` exist, tested only against the fake host | Unvalidated; no host record verifies `skill_discovery` until a live activation probe is reviewed |
| Claude Code, installed plugin | Manifests and optional host validator exist; prose outputs were supplied instructions in a separate experiment | No comparative discovery/host-control result established by these artifacts |
| Cursor, Copilot or other skill hosts | Standalone package contract targets portability | Untested for this matrix; packaging does not establish runtime behavior |

A verified installation is distinct from verified isolation, model selection, question support, delegation, event collection and completion detection. Store these as separate capability booleans with evidence links and timestamps. Unknown remains unknown. The workflow evaluator keeps them in [`evals/workflows/host-evidence/`](../../evals/workflows/host-evidence/), one record per probe, and accepts a host for a mode only when every capability that mode needs is verified. Native-host experiments form a different study when tools or model access differ; keep their results out of the controlled comparison's score.

## Bounds and implementation handoff

First implement a selection-only adapter using real host discovery and frozen installed catalog metadata. Keep candidate access to test expectations disabled. Exercise selection through the first consequential action, then end before product mutations. A dummy selector reading descriptions is an offline fixture, not a model discovery observation. The current runner's explicit loading and `skip_host_skill_discovery` setting must not be reused unchanged and labelled discovery.

The first live group has 12 cases with two repetitions, for 24 parent invocations: `attune` positive, `dispel` positive, `mend` positive, `remedy` positive, `scan` positive, `ultima` positive, `dispel` negative, `ordinary-explicit-only`, `review-or-audit`, `vague-bug`, `missing-sibling` and `changed-target`. Use the protocol's shuffle seed and one serial parent at a time, a 120-second hard timeout, no children and no automatic retries. Maximum parent time is 48 minutes. Selection-only results say nothing about complete workflow quality.

After the adapter preserves load events and scope, expand to all 46 cases with two repetitions in a separately budgeted 92-invocation group. Run the eight overlap/capability cases end to end in a separate 16-invocation group, 600 seconds per parent, same child limits and collection as the main protocol when delegation is available. The maximum parent time for that group is 2 hours 40 minutes. Log legitimate capability stops separately from wrong routing.

Do not expand to a second host until the first host's matrix has interpretable results and the new host passes its own capability/event probes. Retain negative outcomes and ambiguous routes, then prioritize demonstrated misses or unnecessary activations. Change a trigger description only after reproducing the defect and checking its nearest negative or overlapping request. No automatic-activation policy change follows from a low discovery score on intentionally explicit-only skills.
