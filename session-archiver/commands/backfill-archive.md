---
description: Archive every Claude Code session transcript currently on disk into the durable ~/.claude-archive store
---

Run the one-time backfill script and report its summary output to the user:

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/backfill.py"
```

Pass `--force` only if the user explicitly asks to re-archive sessions that already exist in the archive.
