# Reliability and effectiveness delivery order

Planning source: [Improve mana's reliability and measured effectiveness](https://github.com/frankieramirez/mana/issues/72).
Date: 2026-10-17. This is the ordered implementation handoff for the settled decisions. Closing the decision map does not establish that every delivery below has shipped.

Implementation tracking: [Build: Deliver reliable workflows, project controls, and measured effectiveness](https://github.com/frankieramirez/mana/issues/88). Its 41 tickets own the remaining implementation and evidence, including separately resumable benchmark source groups. The build stays open until their acceptance evidence is complete.

Mana 0.43.0 delivers [the debugging reference and focused fixtures](https://github.com/frankieramirez/mana/issues/89), [generic control inspection, mapping and first installation](https://github.com/frankieramirez/mana/issues/90), and [frozen evaluation conditions for supported development cases](https://github.com/frankieramirez/mana/issues/91). The hosted consumer pilot, refresh, broader comparison support and live outcomes remain pending. The bounded ticket scopes take precedence over treating a whole delivery row below as shipped.

## Settled contracts

| Decision | Owning contract |
|---|---|
| Route recurring corrections into code, checks, or judgment | [Correction evidence and pilot promotions](agent-correction-contract.md) |
| Retain, replace or remove comment constraints | [Comment cleanup contract](comment-cleanup-contract.md) |
| Select the project-control pilot, generation/refresh rules and workflow consumers | [Project readiness](project-readiness.md) |
| Bound debugging by runtime evidence | [Debugging procedure](../specs/debugging-procedure.md) |
| Compare workflow outcomes and review effort fairly | [Effectiveness evaluation](../specs/effectiveness-evaluation.md) |
| Separate discovery from execution and host capability | [Discovery and hosts](../specs/discovery-and-hosts.md) |
| Select instruction changes through paired cases and ablation | [Instruction ablations](../specs/instruction-ablations.md) |

## Initial repair batch

The independently specified defects are [source-bound proof execution](https://github.com/frankieramirez/mana/issues/73), [cleanup validation](https://github.com/frankieramirez/mana/issues/74), [authorized and portable audit follow-up](https://github.com/frankieramirez/mana/issues/75), and [fallback map blockers](https://github.com/frankieramirez/mana/issues/85). Their issue and PR records carry delivery status. Package validation, helper regressions and synthetic grader cases establish their stated contracts; they do not establish live model effectiveness.

## Subsequent bounded deliveries

| Order | Delivery and dependency | Completion evidence |
|---|---|---|
| 1a | Implement the stage-loaded debugging reference in Sift and Cast. Uses the settled debugging and cleanup contracts. | Complete standalone packages, synchronized reference, paired boundary/producer cases, disproved-edit preservation, original-path recheck and blocked-runtime evidence. |
| 1b | Extend Leyline with inspect, map and install stages for the current hosted Clankhaven pilot. Uses readiness decisions 78 and 79. | Project-owned generated artifacts, local fake prerequisites, source-bound reports, static and dynamic conformance, and the recorded cold-session return-briefing challenge. Refresh the consumer revision before work. |
| 1c | Extend the existing evaluator for frozen Mana, reference and no-suite conditions. Uses decision 82. | Offline fixture/oracle tests, complete payload inventories, containment and event compatibility probe on an accepted host, frozen controls and held-out manifest. No live comparison starts before these gates. |
| 2a | Add refresh/reconciliation to the generated project controls after 1b. | Rename/delete/configuration drift cases, preservation of confirmed intent and human-owned files, interrupted-setup recovery, and a no-diff second refresh. |
| 2b | Promote one bounded correction per pilot. Ultima's scoped palette assertion rule can proceed independently; Clankhaven's CI release gate depends on 1b. | The known-bad case fails and a legitimate alternative passes through the same mechanism. An actual remote run and relevant branch gate are required before claiming CI enforcement. Retire only replaced guidance. |
| 2c | Add real-host discovery observation after 1c's compatibility work. Uses decision 83. | Actual load events, ordinary-language and negative requests, explicit-only metadata respected, unavailable-capability outcomes separate from wrong routing. |
| 3a | Connect project-control results to Sift, Cast and Scan after 1b and 2a. | Each consumer's claim remains bound to source, surface and executed checks; stale, blocked and partial evidence never becomes a pass. Observe the bounded before/after pilot described in readiness decision 80. |
| 3b | Run the frozen 72-invocation diagnostic effectiveness study after 1c. | Preserve every attempt and all outcome/resource evidence. Human effort remains unmeasured without an actual review cohort. Report diagnostic results and limits, not a general superiority claim. |
| 3c | Run the first bounded instruction experiment after the relevant 1a/initial-repair payloads and 1c machinery are frozen. Uses decision 84. | Current, narrowed and removed variants face the same failure cases and valid alternatives; use the declared keep/revert/inconclusive gates before changing broader instructions. |

Independent branches may run in parallel. Each implementation ticket should name its owning contract, repository and explicit dependencies, with concrete acceptance evidence. External consumer writes and live-study budgets require authorization that actually covers those targets and costs; planning these deliveries does not change permissions.

## Current measurement limits

The planning session inspected the installed host as `codex-cli 0.159.0-alpha.3`. The existing workflow adapter validates other specific versions and fails closed on this one. No live model trial was run by this planning/repair batch. Revalidate containment and the event contract before enabling this host, or run on an already supported host with a fresh probe.

Host acceptance now comes from recorded probe evidence ([issue 99](https://github.com/frankieramirez/mana/issues/99)). Version 0.159.2 keeps its focused and delegated records. A live `run.py --probe-host` run on 2026-10-17 added a Codex CLI 0.163.0 record that verifies process-family termination and everything delegated attempts need. No host has comparative delegated acceptance, because no record shows a challenged thread cap: the 0.163.0 run opened only two children against a cap of two. No runner uses the 0.163.0 delegated acceptance yet, because `delegated_review.py` pins 0.159.2. The probe now holds every child at a gate until the spawn attempts are over, so its next run either shows more children open than the cap or records the host's refusal.

The large comparative study, discovery observations, consumer rollout and new ablations are downstream work. Preserve this distinction in issue closeout and release notes. A merged fix or a completed protocol is useful evidence for its own scope; neither supplies the missing comparative results.
