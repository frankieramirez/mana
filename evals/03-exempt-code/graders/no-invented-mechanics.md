---
type: regex
target: last_message
match: not_contains
weight: 1
flags: i
---
\b(jitter|thundering herd)\b|\btotal\s+(wait|delay|backoff|time)\b|\bup\s+to\s+\d+(\.\d+)?\s*(s|sec|secs|second|seconds|ms)\b|\b\d+(\.\d+)?\s*s\s*,\s*\d+(\.\d+)?\s*s\b|\b\d+\s*,\s*\d+\s*,\s*\d+\s*(s|sec|secs|second|seconds)\b|\b(waits?|sleeps?|pauses?|delays?|backs?\s+off)\s+(for\s+)?\d+(\.\d+)?\s*(s|ms|sec|secs|second|seconds|millisecond|milliseconds)\b
