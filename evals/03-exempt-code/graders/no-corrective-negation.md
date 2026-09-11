---
type: regex
target: last_message
match: not_contains
weight: 1
flags: i
---
(,\s*not\s+(a|an|the)\s|\bis not a bug\b|\bisn'?t a bug\b)
