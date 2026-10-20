# Lean code lens

## Mandate

Use category `architecture`. Find code the project could delete or merge with no loss of behavior. Each extra line has to be read and kept working, so a smaller project is cheaper to change. The remedy always removes or merges code and never adds a layer, helper, option, or framework.

## Where to look

| Pattern | What to look for |
|---|---|
| Dead code | Exports, functions, components, routes, and branches that nothing in the repository reaches. Options, flags, settings, and config keys that no reader consults or no caller ever sets. Shims and fallbacks for paths that no longer exist. |
| Two helpers, one job | Two functions, hooks, or modules that compute the same rule. Keep the one with more callers or the better contract, and name both paths. |
| A dependency the project already covers | A package doing what the standard library, the platform, or another installed dependency already does in a few lines. Name the replacement and every import site. |
| One-implementation abstraction | An interface, base class, factory, registry, or strategy with exactly one implementation and no external consumer. A wrapper whose body only passes its arguments through. |
| Near-copies | Blocks that differ only in names or literals and must change together. One copy already drifting from the other is the strongest form. |

Start from the shared system context and the profile's manifests and entrypoints. Churn and file size point at candidates, never establish them.

## Evidence bar

Before calling anything unused, search the whole repository, not only the audit scope, though findings stay inside the scope: source, tests, fixtures, scripts, config, docs that are executed, build files, and generated registries. Search for the bare name and for string or dynamic references (`getattr`, `import()`, reflection, route tables, dependency injection keys, templates, CLI entry points in manifests). Record each search command and its result in `verification`, and quote the definition plus the registration or manifest line you checked. A symbol published to consumers outside the repository (a package's public API, a documented endpoint, a plugin hook) is not dead without a deprecation decision.

Most findings use evidence_kind `pattern`. Group related instances of one kind of waste with one cause into a single finding: every unused export a removed feature left behind, or every pass-through wrapper over one client.

| Anchor | You must be able to say |
|---|---|
| **100** | Three or more instances, each mechanical: the whole-tree searches return only the definition, nothing reaches it dynamically, and it has no external consumers. For copies, they are verbatim and their callers expect the same behavior. |
| **75** | Three or more instances share the problem, and the repo's own lean example (the helper everyone else already uses, the stdlib call another module makes) is cited in `convention_source`. |
| **50** | One or two instances, or a dynamic reference you could not rule out. Goes to the weaker table. |

Use evidence_kind `trace` only for a single consequential duplication, such as two copies of one business rule that have already diverged. Then the source is one copy, the boundary is where callers choose between them, the consumer is a caller that gets the wrong answer, and the invariant is the rule they both claim to enforce.

## Not a finding

- **Code reached only by tests** when those tests cover a published contract. Code reached only by its own tests is still dead.
- **Intentional extension points** that a decision doc, ADR, or public API commits to keeping. Record the decision status instead.
- **A dependency kept for a documented reason**, such as security fixes, platform support, or a license requirement.
- **Splitting a long function** or a file past some size. Size alone establishes nothing.
- **Defensive code at a trust boundary.** Validation, error handling that prevents data loss, and accessibility support stay.
- **Generated, vendored, or build output.** Fix the generator instead, and only when it is in scope.
- **Style and naming preferences** with no deletion behind them.

## Output

Use the common evidence and output contract in `references/lens-template.md`. `fix` names exactly what to delete or which copy to keep, with every import or call site that changes. Mechanical deletions use action `fix`. A merge that changes a shared contract, a public API, or a dependency used across packages uses action `plan` with remediation, compatibility, rollback, and verification. `wins` can state lines and dependencies removed when you counted them.

```json
{
  "lens": "lean",
  "candidates": [],
  "residual_risks": [],
  "coverage": {
    "status": "partial",
    "files_read": 0,
    "dirs_skipped": [],
    "notes": []
  }
}
```
