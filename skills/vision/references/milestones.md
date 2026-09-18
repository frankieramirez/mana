# Charting milestones

Start with the user's destination and decisions. Read the owning spec or release scope and the relevant project context before drafting. Read an ADR when it constrains a proposed milestone. Separate verified shipped capabilities from work underway and proposed scope; cite the sources behind consequential claims. Missing evidence stays unknown.

Inspect existing work using `references/reconcile.md` step 3c before recommending new planning. A new roadmap must account for work that predates it. Summarize the baseline in **Where we stand**, including the largest gap between current capabilities and the destination.

Each milestone should make a useful decision visible:

- Name the capability or outcome and explain its value.
- Explain why it comes here. Distinguish a dependency from a recommended priority; name work that can proceed independently.
- Define observable completion criteria and the evidence that will satisfy them. Map every destination requirement to a milestone or to verified baseline evidence.
- Identify an unresolved decision or risk when it could change the scope or order. State its consequence and the next way to resolve it.

Choose milestone size to fit independently useful outcomes. A catch-all such as "the rest of the release" needs justified workstreams or a proposed split. Preserve an explicitly chosen release grouping while showing meaningful workstreams within it. Do not turn the roadmap into ticket briefs or duplicate detailed decisions from linked maps.

Use concise paragraphs or checklists as the content warrants. Omit empty fields. Keep distant milestones less detailed, but make the next milestone actionable. Put uncertain future scope under **Not yet planned**, with the decision that would bring it into scope; record exclusions with their reasons.

Ask only about missing choices that materially change the result. Reuse supplied answers. Recommended sequencing and clear existing-work associations are ordinary charting decisions; state assumptions so the user can correct them. `you-pick` authorizes recommended choices on remaining product questions. A draft or review request ends with the proposal; creation or update authorization includes clear member links within that roadmap's scope.

Before publication, check destination coverage, completion evidence, sequencing rationale, and existing-work matches. An unresolved future decision need not block a useful roadmap, but unexplained gaps must be visible.
