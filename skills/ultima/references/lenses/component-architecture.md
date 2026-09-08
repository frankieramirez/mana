# Component architecture lens

## Mandate

You audit the shape of the components and the visual rhythm they produce. A good component hides a decision behind a small interface; a bad one exposes its implementation as props and makes every caller redo the layout math. Your job is to find the interface shapes and the layout habits that repeat across the codebase and cost every new screen something.

## Where to look

| Pattern | What to grep for |
|---|---|
| Boolean prop explosion | Components with several `isX` or `hasX` booleans that combine into states nobody tested: `primary`, `secondary`, and `ghost` all true at once. A `variant` union would replace them. |
| Props that mirror implementation | `className`, `style`, and `onXxx` pass-throughs for every internal node. Components whose props are the CSS properties of their root. |
| Prop sprawl | Interfaces past a dozen props, or a `...rest` spread that hides which HTML attributes reach the DOM. |
| Copy-pasted layout | The same flex or grid wrapper with the same gap and padding repeated instead of a layout primitive. Page shells rebuilt per route. |
| Spacing and type rhythm | Vertical spacing that changes value from section to section with no scale. Heading sizes set per page instead of per level. |
| Responsive gaps | Fixed pixel widths on containers. Breakpoints named in one place and hard-coded elsewhere. Tables and cards with no small-screen branch where the app has a mobile layout. |
| Container and presentation tangles | Components that fetch, transform, and render in one body, when the repo has a hook or a loader convention. |
| Inconsistent composition | Slots in one component, render props in another, `children` overloading in a third, for the same job. |

The comparison is the repo's own best component: the one whose interface is small, whose variants are a union, and whose layout uses the primitives. Cite it in `convention_source`.

## Not a finding

- **Size alone.** A long file with a small interface is fine.
- **Framework-idiomatic patterns**, such as a compound component built the way the library documents.
- **A `className` pass-through on a leaf primitive.** That is the escape hatch primitives are supposed to have.
- **Taste about naming or file layout** with no repeated cost behind it.
- **Timing and lifecycle bugs.** Those are defects for a code review, not architecture.
- **Anything a standards file settles.** Emit with `prior_decision` set.

## Evidence bar

Quote the props declaration, the wrapper, or the fixed value, with `file:line`, for every instance.

| Anchor | You must be able to say |
|---|---|
| **100** | The interface is mechanically checkable: the booleans are declared and no guard prevents the conflicting combination, or the same wrapper markup appears verbatim in the quoted files. |
| **75** | Three or more components share the shape, and one component in the repo has the better shape, cited in `convention_source`. |
| **50** | One or two components, or a design opinion. Goes to the weaker table. |

## Output

Write the full artifact with every schema field to `{run_dir}/{lens_name}.json` (contract: `references/candidates-schema.json`). Return the compact shape: `lens`, `residual_risks`, `coverage`, and `candidates` with title, strength, effort, instance count, the first three instances, `convention_source`, and `prior_decision`. No prose outside the JSON.

For interface candidates, `before` is the current props declaration and `after` is the union or the primitive that replaces it. Keep both short enough to read on a card.

```json
{
  "lens": "component-architecture",
  "candidates": [],
  "residual_risks": [],
  "coverage": {"files_read": 0, "dirs_skipped": [], "notes": []}
}
```
