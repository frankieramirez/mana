---
max_turns: 8
timeout_seconds: 180
allowed_tools: [Skill]
model: opus
runs: 3
---
This returns the wrong result when the list is empty. Fix it.

```python
def average(values):
    total = 0
    for v in values:
        total += v
    return total / len(values)
```
