# Build effort candidate

Read the parent with `view PARENT_ID`, its members with `children PARENT_ID`, and open members with `view MEMBER_ID` through the bundled tickets script and resolved adapter flags.

`children` gives only id, state, title, and url. For an open effort, count members by state, then `view` each open member: its `assignees` and `labels` lines are the only source for the checks below. A member already assigned to the person driving this session is the effort's available ticket before anything else, since it is work they have started; say it is already theirs. Otherwise, for each open member with no assignee whose labels carry the ready label, run `blocked MEMBER_ID`; the first one with no open blocker, in build order, is the available ticket. Build order comes from the parent's **Build order** section, read with `view PARENT_ID`.

Resolve the current tracker identity before treating an assignment as yours, using `gh api user --jq .login` on GitHub or the configured tracker identity elsewhere. If identity cannot be read, report it as unknown and do not assume a held ticket is yours.

For a progress route, inspect blockers of the remaining ready members and linked PRs before reporting blocked or awaiting-review counts. Use the PR reference when interpreting PR state. Do not infer those counts from assignment alone.
