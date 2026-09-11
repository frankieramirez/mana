---
type: llm
focus: last_message
weight: 1
---
The answer fixes a Python function that raises ZeroDivisionError on an empty list.

PASS only if all three hold:

1. The answer contains a version of `average` that does not divide by zero when `values` is empty. Returning 0, returning 0.0, returning None, or raising a clear ValueError are all acceptable fixes.
2. Behavior on a non-empty list is unchanged: the function still returns the arithmetic mean.
3. The answer stays a code answer. It does not rewrite the wording of the question, does not critique the question's writing style or register, and does not return a de-slopped or "more human" version of the prompt text.

Claim 3 is the one under test. This case checks that a prose-rewriting skill stays out of a pure code task.

Claim 3 is about prose editing only. Correcting the premise is not a violation: pointing out that an empty list raises ZeroDivisionError rather than returning a wrong number is accurate technical feedback and PASSES. Explaining the fix, discussing the choice between returning a value and raising, or noting a caveat about generators are all normal code-review remarks and PASS.
