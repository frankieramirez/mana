# Report progress

Write the result as markdown, not as a code block. A cell holds one line, and links go in bare so the terminal renders them. Refer to milestones by name and issues by title with the link wrapped inside.

### Vision

| | |
|---|---|
| **Destination** | one line |
| **Milestones** | done/total, then the names in order with each status |
| **Current** | name and status, then maps closed/open and efforts delivered/open |
| **Left** | the current milestone's Left line |
| **Unattached** | count of maps and efforts naming no milestone, or `none` |
| **Unplanned** | count of Not yet planned lines, or `none` |

**Next step:** \<action> on \<milestone or ticket with link>. \<One sentence on why.>

**Prompt:** `\<one line that starts it>`

Name any milestone whose status changed this run, in one sentence above the table. Next step is the first row that holds for the current milestone. When no milestone is current, only the last two rows apply:

| Condition | Next step | Prompt |
|-----------|-----------|--------|
| An open map has a frontier ticket | Resolve the map ticket | `Resolve <ticket URL> on its map.` |
| An open map has no frontier ticket | Inspect the map | `Inspect <map URL> and resolve what keeps it open.` |
| An open effort has an available ticket | Implement the ticket | `Implement <ticket URL>, following its brief.` |
| A closed map has no effort | Plan implementation from the map | `Use the completed planning map <map URL> to propose the implementation work, keeping the map as the planning source.` |
| An open effort has nothing available | Check the build effort | `Check progress and close out the build effort at <parent URL> once the pending work is complete.` |
| The milestone is `planned` | Chart a new planning map | `Chart a map toward <milestone outcome>, serving milestone <name> on <roadmap URL>.` |
| Every milestone is `done` and Not yet planned has lines | Add the next milestone | `Add milestone <first unplanned line> to the roadmap at <roadmap URL>.` |
| Every milestone is `done` and nothing is unplanned | none | Say the destination is reached and omit the prompt |

The prompt describes an ordinary task without depending on another installed skill. The report completes a roadmap-only request. Continue further work when it is part of the user's explicit request.

