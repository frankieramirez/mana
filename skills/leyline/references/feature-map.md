# Draft the first feature map

Load during Map, after inspection. This first generator accepts one explicit `briefing` feature with `briefing.return-summary` and `briefing.no-activity`. It does not infer product intent or rewrite tests. Other features and existing controls need a focused project adaptation.

Use [references/recipes/typescript-node.md](references/recipes/typescript-node.md) and its example specification. Keep that specification and the review map outside the target checkout. Source paths and the break patch are relative to the checkout. The test files must already register each scenario with a literal `scenario` call whose test name contains its stable id. Preserve the existing assertions when adding bindings.

```bash
bash "<SKILL_DIR>/scripts/generate.sh" map <repo> --spec <spec.json> --out <map.json>
```

Map reads source and test files, verifies the declared patch can apply, and writes a review artifact. It does not execute project code or modify the target. The artifact contains exact candidate file contents, existing blob identities, the source revision and file manifest, and a generator/template fingerprint. Review the output paths and command arrays before installation. Commands belong in the generated project adapter configuration; feature and scenario records store intent and reach data, never execution outcomes.

All generated feature intent remains `proposed`. If code contradicts an approved expectation, preserve that expectation and name the unresolved choice. A green run is execution evidence, not approval of product intent.
