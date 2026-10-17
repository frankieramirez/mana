# First TypeScript/Node recipe

Load during Map and Install. This recipe copies a small adapter into an ESM Node project; it does not install a shared runtime dependency. It needs Node 22.13 or newer, Git, and the project's existing test runner. Generation itself uses Bash and Python's standard library.

Start from [references/recipes/briefing-map.example.json](references/recipes/briefing-map.example.json). Replace its source roots, bindings, prerequisite paths, and command arrays with inspected project facts. Keep the two proposed scenarios' claims within their actual assertions. The example's paths are illustrative and must exist in the target; the generator refuses missing sources and bindings.

The runner keeps the project's Vitest command and writes its JSON reporter output to `{report}`. For example, use an argv array containing `node`, the installed Vitest executable, `run`, the relevant test path, `--reporter=json`, and `--outputFile={report}`. The adapter reads each assertion's actual status and stable scenario id. Do not synthesize success from test discovery, a process exit, or a list of expected cases. An assertion name must contain exactly the scenario it proves.

Where existing tests use Vitest's `test` function, import that same function as `scenario` and give the two selected tests their stable ids. Preserve their bodies, setup hooks, and teardown. This changes registration names without adding a second test DSL. Inspect the resulting diff and run the original assertions.

`prepare.argv`, when supplied, runs inside each private source snapshot. Use the existing frozen install command, with its actual network requirements. Dependencies are not linked from a shared mutable install. `prerequisites` names required repository-relative files after preparation; an absent file produces incomplete verification and names the prerequisite. Paths cannot escape the checkout. Browser availability and service-specific readiness still need explicit project fixture checks; a file existing does not prove a browser launched.

`release` declares additional project release obligations as an argv array and either `vitest-json` or `exit` format. The mapped feature also runs. Null release configuration returns incomplete for `release`, because feature success cannot establish the project's full release gate. Exit-format release checks establish only that declared command's result and do not stand in for mapped scenario execution.

The generated control conservatively widens `changed` to the complete mapped feature. It snapshots tracked and untracked source, records the checked manifest, and compares source after execution. Reports retain logs outside the removed snapshot. Inspect environment and dependency limits in the report; a source digest does not by itself fingerprint every external input. Unsupported symlinks or submodules require a focused project adapter.

The runtime template is [references/recipes/control.ts.template](references/recipes/control.ts.template). Once installed, it and the generated configuration are hand-maintained project code. A later generator must compare ownership history and propose a patch, never replace those files wholesale.
