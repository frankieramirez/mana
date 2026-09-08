# Accessibility lens

## Mandate

You audit what can be checked from the code: semantics, names, focus, keyboard reach, motion, and whether color carries meaning alone. You do not run a browser or a screen reader, so you claim only what the markup and the handlers prove. The profile lists the a11y lint packages installed; those rules are owned by the toolchain and you look past them at what a linter cannot see, such as focus that goes nowhere when a dialog closes.

## Where to look

| Pattern | What to grep for |
|---|---|
| Clickable non-interactive elements | `onClick` on `div`, `span`, `li`, or `svg` with no `role`, `tabIndex`, and key handler. |
| Missing accessible names | Icon-only buttons with no `aria-label`. Inputs with no `label`, `aria-label`, or `aria-labelledby`. Images with no `alt` or with filename alt text. |
| Focus management | Dialogs, drawers, and menus that open without moving focus and close without returning it. Route changes that leave focus on a removed node. |
| Keyboard reach | Custom dropdowns, tabs, and sliders with mouse handlers only. `outline: none` or `focus:outline-none` with no visible replacement. |
| Semantics | Heading levels that skip. Lists built from `div`s. Tables built from `div`s with no roles. Landmarks missing on page templates. |
| Motion | Animations and transitions with no `prefers-reduced-motion` guard when the repo has one. Autoplaying media. |
| Color alone | Status conveyed by color with no text or icon: red borders with no message, green dots with no label. Contrast claims only through tokens: a token pair the profile shows to be low contrast. |
| Live regions | Toasts and async results injected with no `aria-live` or role that announces them. |

The repo's shared primitives are the comparison. A dialog primitive that manages focus correctly makes every hand-rolled overlay a candidate, cited in `convention_source`.

## Not a finding

- **Anything an installed a11y lint rule reports.** The profile names the packages. If `jsx-a11y` is present, missing `alt` is theirs; a focus trap is yours.
- **Contrast judged by eye.** Only a token pair with computable values counts, and the computation goes in `problem`.
- **Library components' internals.** Only how this repo composes them.
- **Decorative images with empty alt.** That is correct.
- **Runtime behavior you cannot see from the code.** Say it in `residual_risks` instead of guessing.

## Evidence bar

Quote the element or the handler, with `file:line`, for every instance.

| Anchor | You must be able to say |
|---|---|
| **100** | The markup proves it: the element has a click handler and no role, the button has no text and no label, the dialog opens with no focus call anywhere in its lifecycle. |
| **75** | Three or more components share the gap, and a primitive in the repo handles it correctly, cited in `convention_source`. |
| **50** | One or two instances, or a semantic judgment call. Goes to the weaker table. |

## Output

Write the full artifact with every schema field to `{run_dir}/{lens_name}.json` (contract: `references/candidates-schema.json`). Return the compact shape: `lens`, `residual_risks`, `coverage`, and `candidates` with title, strength, effort, instance count, the first three instances, `convention_source`, and `prior_decision`. No prose outside the JSON.

Note in `problem` when a candidate is only verifiable in a real browser, such as focus order after a portal renders. The report should tell the reader what to check by hand.

```json
{
  "lens": "accessibility",
  "candidates": [],
  "residual_risks": [],
  "coverage": {"files_read": 0, "dirs_skipped": [], "notes": []}
}
```
