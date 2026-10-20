# Install a reviewed candidate

Load during Install. Installation requires existing authority to edit this target repository. A request to install the control covers the generated files and named root/package integration. Reuse that authority without asking again. A read-only request stays at inspection and a reviewable map.

```bash
bash "<SKILL_DIR>/scripts/generate.sh" install <repo> --map <map.json>
```

The installer verifies the map and generator identities, compares the checked source, and rejects occupied output paths. It preserves an existing Control pointer or verify command rather than replacing it. It checks the complete candidate with the bundled static checker before writing project files. Root guidance retains its surrounding bytes; the package manifest retains existing keys and gains only the verify entry, with JSON formatting normalized.

The result includes a project-owned control entry and configuration, proposed records, a declared break patch, control instructions, the root pointer with its read-first sentence, the package command, and an installation record in `docs/agents/readiness.md`. The ledger records source and generator identities, installed blob hashes, ownership, and the still-pending challenge. Ordinary write failures and handled SIGINT/SIGTERM interruptions roll back unchanged files still owned by this invocation. Existing files are displaced into temporary recovery files and checked before exclusive publication, so a concurrent edit or competing installation is not overwritten. If another writer prevents restoration, the installer retains the displaced file and prints its recovery path. This protects observed installation conflicts; it does not serialize continuing writes through an already open file descriptor. An uncatchable process termination can leave partial files or recovery files and requires inspection before recovery.

Reinstalling the exact matching outputs is a no-op. A changed source, edited output, changed generator, or competing control requires a new reviewed adaptation. This command performs first installation. Later drift and an interrupted installation go through [references/refresh.md](references/refresh.md).

Installation returns `candidate`, never `verified`. Commit the reviewed candidate when commit authority exists before using the HEAD-based dynamic checker. Keep the user's checkout unchanged during execution, retain its source identity and the raw reports, and proceed to [references/challenge.md](references/challenge.md).
