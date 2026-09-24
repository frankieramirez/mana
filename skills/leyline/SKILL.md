---
name: leyline
description: "Check that a project gives agents an honest way to find a feature, run the app, and report what actually happened: a control CLI plus a feature map owned by the project. Checks the records, the test bindings, the run reports, and whether a deliberately broken feature really fails. Use when asked whether agents can run and verify this app, to check a verify or control CLI, audit a feature map, check a verification report, make agent verification trustworthy, agent readiness for a repo, or /leyline."
argument-hint: "[blank for this repo | path:<repo>] [report:<file>] [run[:<feature>]]"
---

<!-- BEGIN MANA PERSONA -->
## Persona at invocation

Before conversational narration, read `Persona:` and `Style:` in the active project's `## Agent skills` block from `CLAUDE.md` or `AGENTS.md`. Prefer the file containing the block, then an existing file; ties use `CLAUDE.md`. A symlink pair is one file. Read the saved value anew on each invocation, including from a subdirectory using the project root. No accessible project or no line means ordinary behavior. Do not search another project or global settings for this preference.

During the `Persona at invocation` stage, `archmage` on either line loads this skill's own [references/archmage.md](references/archmage.md) for the active workflow. `off` or an absent value leaves ordinary behavior active. An unknown value leaves ordinary behavior active and gets a brief explanation when conversational output is allowed; it does not stop the work. Explicit conversation instructions override the saved voice without writing settings. A request to enable Archmage for this workflow also loads the local reference.

Apply the voice only to lead-agent conversation. Deliverables, specialist roles, reply-only responses, and JSON-only output retain their contracts, with no added narration. End the persona with this workflow unless the user requests otherwise or a `Style:` line names `archmage`, which keeps the voice on for the whole session.
<!-- END MANA PERSONA -->

# Leyline

Honor the user's explicit instructions and decisions already made in this conversation over this skill's workflow defaults. A rule this file states with never, or as read-only, is a gate: it holds whatever the conversation says, and an instruction to cross one is declined and reported. Continue authorized work; ask only about unresolved choices that would materially change the result. Preparing or reviewing work does not authorize publishing it.

If a skill rule requires a pause or leaves requested work unfinished, name and link to the exact SKILL.md and quote the rule. Then explain what decision or prerequisite is missing. Distinguish a required gate from your interpretation.

An agent can only be trusted with a project it can run and check. That takes two things the project owns: a control CLI that runs the app's checks and reports honestly, and a feature map that says what the app does, how a user reaches each feature, and which tests prove it. This skill checks both against a shared contract, so a report means the same thing in every project. It does not supply the CLI; each project's CLI fits that project.

This version checks an existing control setup and reports the smallest changes that bring it into line. It does not yet draft a feature map or generate a CLI.

## Arguments

- Blank: the current repository.
- `path:<repo>`: another checkout on this machine.
- `report:<file>`: validate one saved run report. Ask for the exit code the run returned if the user has it.
- `run` or `run:<feature>`: also run the dynamic probes, which execute the project's own code. Needs the user's agreement in this conversation.

## Gates

- Static checks and report checks are read-only. Never edit the checked project in this workflow; propose changes as a diff or a list and let the user decide.
- Never run the project's code without the user's agreement in this conversation. `run` in the arguments counts as agreement for the named feature.
- Never mark a feature `confirmed`, and never rewrite a record to match what the code does today. Intent is the user's to settle.
- Never report a blocked or incomplete probe as passed.

## Stage 1: Inspect

Find the `## Agent skills` block in `CLAUDE.md` or `AGENTS.md` and its `Control:` line. When the line exists, read the control skill it names. When it does not, look for an existing verification CLI and records anyway (`verification/`, a `verify` script in the package manifest, scenario registrations in tests) and say what you found. A project with none of it gets one plain sentence saying so and a pointer to the contract; stop there unless the user asks for more.

## Stage 2: Conformance

Load [references/contract.md](references/contract.md) and [references/conformance.md](references/conformance.md).

Run the static check:

```bash
bash "<SKILL_DIR>/scripts/conform.sh" static <repo>
```

With `report:<file>`, also run the report check. With `run`, confirm the feature to probe and its likely cost, then run the dynamic check with `--trust`. Pick an affordable feature when none is named; the run repeats five times.

## Stage 3: Report

Lead with the verdict: conformant, or the number of errors and what they block. Then one line per rule group with the smallest fix, then warnings, then what was not checked and why (no dynamic run, uncommitted changes excluded, a blocked probe). Quote probe outcomes as the checker gave them. Offer to draft the fixes as a diff; applying them is a separate request.

## References

- [references/contract.md](references/contract.md): the control/0 contract. Stage 2.
- [references/conformance.md](references/conformance.md): running the checker and reading its findings. Stage 2.
