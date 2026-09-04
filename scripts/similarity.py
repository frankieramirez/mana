#!/usr/bin/env python3
"""Dev-only: how close each formerly-forked file still is to its origin.

Usage: scripts/similarity.py [path-to-compound-engineering-skills-dir]
Default origin: the compound-engineering plugin cache under ~/.claude/plugins.
Ratios above 0.30 mean the file still reads as a copy.
"""
import difflib, glob, os, sys

origin = sys.argv[1] if len(sys.argv) > 1 else max(
    glob.glob(os.path.expanduser("~/.claude/plugins/cache/every-marketplace/compound-engineering/*/skills")), default=None)
if not origin or not os.path.isdir(origin):
    sys.exit("origin skills dir not found; pass it as the first argument")

root = os.path.join(os.path.dirname(__file__), "..")
pairs = [
    ("skills/scan/references/diff-scope.md", "ce-code-review/references/diff-scope.md"),
    ("skills/scan/references/subagent-template.md", "ce-code-review/references/subagent-template.md"),
    ("skills/scan/references/findings-schema.json", "ce-code-review/references/findings-schema.json"),
    ("skills/scan/references/finish-review.md", "ce-code-review/references/finish-review.md"),
    ("skills/scan/SKILL.md", "ce-code-review/SKILL.md"),
    ("skills/remedy/SKILL.md", "ce-resolve-pr-feedback/SKILL.md"),
    ("skills/remedy/SKILL.md", "ce-resolve-pr-feedback/references/full-mode.md"),
    ("skills/remedy/references/evaluation-rubric.md", "ce-resolve-pr-feedback/references/evaluation-rubric.md"),
    ("skills/remedy/references/fixer-prompt.md", "ce-resolve-pr-feedback/references/agents/pr-comment-resolver.md"),
    ("skills/remedy/scripts/pr-threads", "ce-resolve-pr-feedback/scripts/get-pr-comments"),
]
for ours, theirs in [
    ("protection-warrior", "correctness"), ("subtlety-rogue", "security"),
    ("havoc-demon-hunter", "adversarial"), ("marksmanship-hunter", "testing"),
    ("fire-mage", "performance"), ("restoration-shaman", "reliability"),
    ("retribution-paladin", "project-standards"), ("unholy-death-knight", "data-migration"),
    ("balance-druid", "maintainability"), ("demonology-warlock", "api-contract"),
    ("windwalker-monk", "julik-frontend-races"), ("lore-bard", "previous-comments"),
    ("augmentation-evoker", "agent-native"),
]:
    pairs.append((f"skills/scan/references/personas/{ours}.md",
                  f"ce-code-review/references/personas/{theirs}-reviewer.md"))

worst = 0.0
for ours, theirs in pairs:
    a, b = os.path.join(root, ours), os.path.join(origin, theirs)
    if not (os.path.exists(a) and os.path.exists(b)):
        print(f"  --   missing  {ours} vs {theirs}")
        continue
    A, B = open(a).read(), open(b).read()
    r = difflib.SequenceMatcher(None, A, B).ratio()
    worst = max(worst, r)
    flag = "  " if r < 0.30 else "!!"
    print(f"{flag} {r:.2f}  {len(A.split()):5d}w / {len(B.split()):5d}w  {ours}")
print(f"\nworst: {worst:.2f}")
sys.exit(0 if worst < 0.30 else 1)
