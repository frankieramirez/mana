---
type: regex
target: last_message
match: contains
weight: 1
---
don't retry on 4xx — the server won't change its mind
