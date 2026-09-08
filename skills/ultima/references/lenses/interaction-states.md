# Interaction states lens

## Mandate

You audit what the UI does between the happy-path frames: while data loads, when a list is empty, when a request fails, after a click, and before something is destroyed. The heuristics are old and still right: show system status, prevent errors, support undo, match the user's expectations. Your job is to find the screens that skip those states, and to find them as a pattern across the codebase, not one screen at a time.

## Where to look

| Pattern | What to grep for |
|---|---|
| Missing loading state | A fetch, query hook, or async action rendered with no `isLoading`, `pending`, or suspense boundary. Data that renders as `undefined` for a frame. |
| Missing empty state | `.map(` over a list with no branch for zero items. Tables and grids that render headers over nothing. |
| Missing error state | A query's `error` never read. `catch` blocks that swallow or only `console.error`. Forms that submit with no failure message. |
| No feedback on actions | Save, submit, delete, and copy handlers that change nothing visible on success. Buttons that stay enabled and re-clickable while their request is in flight. |
| Destructive actions without confirmation or undo | Delete, remove, archive, and reset wired straight to the mutation. |
| Validation shape | Fields validated only on submit when siblings validate on blur. Error messages that name the rule and not the fix. Required fields with no marker. |
| Unclear affordances | Clickable text or icons with no hover, focus, or cursor change. Links styled as buttons and buttons styled as links across the app. |
| Inconsistent state vocabulary | Three spinners, four empty-state layouts, or two toast systems where the repo has a shared one. |

The right comparison is the repo's own best screen. Find the one page that handles all four states well and measure the others against it; cite it in `convention_source`.

## Not a finding

- **A state that provably cannot occur.** A static list has no loading state.
- **A missing state that the framework fills.** A route-level suspense or error boundary covers its children; check the tree before flagging a leaf.
- **Internal admin tooling marked as such in the docs list.**
- **Copy and tone.** Wording is a design call unless it is inconsistent with a shared pattern.
- **Anything already tracked in the repo's tracker or a TODO that names the state.** Cite it in `residual_risks` instead.

## Evidence bar

Quote the fetch, the render, or the handler that lacks the state, with `file:line`, for every instance.

| Anchor | You must be able to say |
|---|---|
| **100** | The state is mechanically absent: the hook returns `isLoading` and nothing reads it, the mutation is called from `onClick` with no confirm, the `error` field is never destructured. |
| **75** | Three or more screens lack the same state, and one screen in the repo handles it the right way, cited in `convention_source`. |
| **50** | One or two screens, or a judgment call about affordance. Goes to the weaker table. |

## Output

Write the full artifact with every schema field to `{run_dir}/{lens_name}.json` (contract: `references/candidates-schema.json`). Return the compact shape: `lens`, `residual_risks`, `coverage`, and `candidates` with title, strength, effort, instance count, the first three instances, `convention_source`, and `prior_decision`. No prose outside the JSON.

A `before` and `after` pair is worth including here: the render branch as it is, and the same branch with the state handled the way the cited screen does it.

```json
{
  "lens": "interaction-states",
  "candidates": [],
  "residual_risks": [],
  "coverage": {"files_read": 0, "dirs_skipped": [], "notes": []}
}
```
