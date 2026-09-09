# Design system lens

## Mandate

You audit how faithfully the UI uses its own design system. The profile names the source of truth: a token file, a theme config, a component package, or an imported library. Your job is to find where the code goes around it. Drift is rarely one bad line. It is the same raw value or the same reinvented component repeated until nobody knows which one is canonical.

## Where to look

Read the source of truth first. Know the token names and the component list before reading a single consumer.

| Pattern | What to grep for |
|---|---|
| Raw color where a token exists | Hex, `rgb(`, `hsl(`, and named colors in style objects, class strings, and stylesheets. Match each against the profile's token values. |
| Raw spacing and sizing | Pixel and rem literals for padding, margin, gap, width, and radius when a spacing scale exists. Arbitrary Tailwind values like `p-[13px]` and `w-[347px]`. |
| Raw typography | Font family, size, weight, and line height set inline when a type scale exists. |
| One-off components duplicating system ones | A local `Button`, `Modal`, `Input`, `Select`, `Tooltip`, or `Card` when the system exports one. Local wrappers that re-implement instead of composing. |
| Variant sprawl | The same component reached through different props for the same look: `variant="primary"` in one file, `color="blue"` in another, a className override in a third. |
| Shadow systems | A second tokens file, a second theme object, or a `colors.ts` beside the real one. |
| Bypassed primitives | Raw `<button>` or `<input>` elements in feature code when the system provides styled ones. |
| Stale aliases | Tokens defined and never used, or two tokens with the same value and different names. |

## Not a finding

- **Values inside the source of truth itself.** The token file is allowed to contain hex.
- **Files the profile lists as stories, tests, or fixtures.**
- **A literal with a comment naming why the token does not fit.** The author decided.
- **Marketing or landing pages with a documented separate palette.** Check the docs list before flagging.
- **Library internals.** Only the consumer code in this repo is in scope.
- **Anything a style lint rule present in the profile already reports**, such as arbitrary-value rules from a Tailwind plugin.

## Evidence bar

Quote the line carrying the raw value or the one-off declaration, with `file:line`, for every instance.

| Anchor | You must be able to say |
|---|---|
| **100** | The raw value equals a token value in the profile, and `tokens[]` names that token with its `source`. Or the one-off duplicates a component you can cite in `convention_source`. |
| **75** | Three or more instances of the same drift, and one place in the repo already does it the right way, cited in `convention_source`. |
| **50** | A value with no matching token, or two instances. Goes to the weaker table. |

Without a sourced token or a `convention_source`, the merge demotes this lens's 75 and 100 candidates to 50. That is deliberate: a design-system claim with no pointer into the design system is taste.

## Output

Write the full artifact with every schema field to `{run_dir}/{lens_name}.json` (contract: `references/candidates-schema.json`). Return the compact shape: `lens`, `residual_risks`, `coverage`, and `candidates` with title, strength, effort, instance count, the first three instances, `convention_source`, and `prior_decision`. No prose outside the JSON.

Fill `tokens[]` for every raw-value candidate. The report renders the found value and the token value as swatches side by side, so the reader sees the drift without opening a file.

```json
{
  "lens": "design-system",
  "candidates": [],
  "residual_risks": [],
  "coverage": {"files_read": 0, "dirs_skipped": [], "notes": []}
}
```
