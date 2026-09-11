---
max_turns: 8
timeout_seconds: 180
allowed_tools: [Skill]
model: opus
runs: 3
---
Rewrite the prose in this doc section so it doesn't sound like AI. Leave the code and the error text exactly as they are. Return only the rewritten section, with no commentary.

## Retry behavior

The client leverages an exponential backoff strategy in order to handle transient failures gracefully — this ensures robust behavior under load.

```python
for attempt in range(MAX_RETRIES):
    try:
        return session.post(url, timeout=5.0)
    except TimeoutError:  # don't retry on 4xx — the server won't change its mind
        sleep(2 ** attempt)
```

If retries are exhausted the caller sees `ConnectionError: max retries (5) exceeded — giving up`. It is worth noting that this is not a bug, it's the intended contract.
