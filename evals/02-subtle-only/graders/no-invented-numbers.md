---
type: regex
target: last_message
match: not_contains
weight: 1
flags: i
---
\b\d+(\.\d+)?\s*(ms|millisecond|percent|%|x faster|seconds?)\b
