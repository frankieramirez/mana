---
type: regex
target: last_message
match: contains
weight: 1
flags: i
---
(340\s?ms[\s\S]{0,400}45\s?ms|45\s?ms[\s\S]{0,400}340\s?ms)
