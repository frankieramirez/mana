# Vision regression scenarios

Run each case in a fresh session with the installed `skills/vision/SKILL.md` and the raw input below. Use a temporary workspace and simulated tracker; no live writes. Save the proposed roadmap, report, and operation log. Grade behavior using `rubric.md` after the run. A fixture-only run cannot verify real tracker writes or concurrency.

`ultima-first-run.md` is a reduced reproduction of Ultima #161 and #137. The supplied tracker snapshot is sufficient for this draft request; do not fetch live project state.

For additional cases, vary that input:

- **Partial delivery:** An existing labelled roadmap has criteria for primitives and Vite/Next.js installation. Its one linked effort is closed and proves only primitives. Ask for a report without writes. Installation stays unverified and the destination is not declared reached.
- **Legacy discovery:** Remove the pointer and label; retain `Work kind: roadmap` on one open issue with Destination and Milestones. Ask for an update. Discover it through the legacy search, ensure the label before removing the marker, and preserve user content.
- **Label discovery:** Remove the marker from that issue and retain the label. It remains discoverable. Two open valid labelled roadmaps require selection; a failed lookup cannot justify creating a duplicate.
- **Conflicting membership:** Give the matching map a Milestone line for another roadmap. It is a candidate requiring a decision, never silently reassigned. Do not suggest duplicate planning.
- **Write conflict:** Simulate a member body changing between snapshot and update. Reread and retry once; a second conflict leaves the link unresolved. Report saved links if a later roadmap operation fails.
- **Explicit confirmation:** Add a user Confirmed done reason despite missing proof. Preserve done and disclose that it is user-confirmed. Reopen removes that override and derives status from actual evidence.
