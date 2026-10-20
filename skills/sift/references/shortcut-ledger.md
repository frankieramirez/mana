# Shortcut ledger

Load at Stage 4. A deliberate shortcut in code carries a one-line comment, `shortcut: <the limit>, <when to revisit>`. The ledger collects them so a deferral stays visible instead of turning permanent.

## Collect

Search tracked files for markers that open a comment, so prose that only describes the convention stays out:

```bash
git grep -nE '(#|//|/\*|--|<!--) ?shortcut:'
```

Add the comment prefixes of any other language the repo uses. Read each hit and drop the ones that are no deferral, such as a note about a keyboard shortcut. The text after `shortcut:` up to the first comma is the limit, and the rest is the trigger. A marker with nothing after the limit gets the tag `no-trigger`, because nothing tells anyone when to come back to it.

## Present

One line per marker, grouped by file, in file and line order:

```
<file>:<line> limit: <the limit>. revisit: <the trigger, or no-trigger>.
```

End with `<N> markers, <M> with no trigger.` With no hits, say `No shortcut markers.` and stop.

## File

Offer to file the markers as tickets. Filing creates tracker issues, so wait for the maintainer's answer unless the request already asked to file them. `you-pick` does not answer this question. File only the markers the maintainer picks, or all of them when they say so.

Before filing a marker, run `find` with its verbatim comment text. A hit in any state means the marker is already tracked: skip it and report that issue's id. File each remaining marker with `create`, labelled with the `needs-triage` string, the body on stdin:

```bash
bash "<SKILL_DIR>/scripts/tickets.sh" <adapter flags> find "<verbatim marker text>"
bash "<SKILL_DIR>/scripts/tickets.sh" <adapter flags> create "Shortcut: <the limit> in <file>" --label <needs-triage string>
```

The body starts with the AI triage line, then names the file and line, the limit, the trigger or `no-trigger`, and the marker text verbatim so a later `find` matches it. The new issues enter Stage 1 like any other report. Report what was filed, with each id and URL, and what was skipped as already tracked.
