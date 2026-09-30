# Run artifacts

Load at Full step 1 or Targeted step 1 before creating artifacts.

Every artifact this run produces lands in one directory under `/tmp/remedy-<uid>/`. Create it before anything else:

```bash
SCRATCH_ROOT="/tmp/remedy-$(id -u)";
if [ -L "$SCRATCH_ROOT" ]; then echo "unsafe scratch root symlink: $SCRATCH_ROOT" >&2; exit 1; fi;
install -d -m 700 "$SCRATCH_ROOT" || exit 1;
if [ -L "$SCRATCH_ROOT" ] || [ ! -O "$SCRATCH_ROOT" ]; then echo "scratch root not owned by current user" >&2; exit 1; fi;
chmod 700 "$SCRATCH_ROOT" || exit 1;
RUN_ID=$(date +%Y%m%d-%H%M%S)-$(head -c4 /dev/urandom | od -An -tx1 | tr -d ' ');
RUN_DIR="$SCRATCH_ROOT/$RUN_ID";
(umask 077; mkdir -p "$RUN_DIR/scouts") || exit 1;
echo "$RUN_DIR"
```

What the run writes there, and when:

| File | Written at | Contents |
|------|-----------|----------|
| `fetch.json` | Step 1 | The `pr-threads fetch` output |
| `items.json` | End of step 3, updated in steps 4, 4b, and 7 | One object per new item: identity, location, `read_depth`, verdict, evidence, the change note or the explanation; later the fixer `outcome`, `verified`, and `resolved` |
| `scouts/<cluster>.json` | Step 3, large batches only | Scout evidence per file cluster |
| `fixes.diff` | Step 4b | The combined diff the verifier reads |
| `verify.json` | Step 4b | The verifier's return |
| `summary.md` | Step 9 | The summary block, verbatim |
| `metadata.json` | Step 9 | PR, branch, head before and after, patch-id, counts by verdict, resolved and left-open thread ids, push and CI state |

A later run on the same PR reads `metadata.json` and `items.json` in step 2. Nothing is deleted.
