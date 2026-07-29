# session-archiver

Claude Code plugin that archives session transcripts into a durable,
normalized local store at `~/.claude-archive/`, outside Claude Code's own
retention policy (`~/.claude/projects/` transcripts are auto-deleted after
`cleanupPeriodDays`, default 30 days).

## What it does

- Registers a `SessionEnd` hook (`scripts/archive_session.py`) that archives
  each session's transcript the moment it ends.
- Ships `/session-archiver:backfill-archive` to archive every transcript
  still on disk today, before more age out.
- Writes one JSON file per session at
  `~/.claude-archive/<encoded-project-path>/<session-id>.json`, preserving
  every field of every transcript line untouched under a stable wrapper:

```json
{
  "schema_version": 2,
  "session_id": "...",
  "project_path": "...",
  "archived_at": "2026-07-22T...",
  "source_transcript_path": "~/.claude/projects/.../<id>.jsonl",
  "turns": [ /* raw transcript lines, as-is */ ],
  "subagents": [
    {
      "agent_id": "...",
      "meta": { /* raw agent-<id>.meta.json, as-is */ },
      "turns": [ /* raw subagents/agent-<id>.jsonl lines, as-is */ ]
    }
  ],
  "tool_results": {
    "<hash>": "raw contents of tool-results/<hash>.txt, only for hashes referenced in turns/subagents"
  }
}
```

`v1` archives have no `subagents`/`tool_results` fields — treat their absence
as "not captured," not as "empty." `schema_version: 2` adds:

- **`subagents`** — Task-tool subagent runs, normally written to a sibling
  `subagents/agent-<agentId>.jsonl` (+ `.meta.json`) next to the main
  transcript and never inlined into it. Without this, delegated-agent work
  ages out with the rest of `~/.claude/projects/` on the same
  `cleanupPeriodDays` timer.
- **`tool_results`** — large tool outputs Claude Code offloads to
  `tool-results/<hash>.txt`, referenced by hash from `turns`/`subagents`
  instead of inlined. Only hashes actually referenced are archived, so this
  doesn't sweep in unrelated leftover files.

## Not doing

- No reconstruction of already-pruned sessions from `history.jsonl` —
  prompt-only, no assistant turns survive there.
- No cloud sync, no SQLite index — flat JSON files per session.
- No retention/cleanup of the archive itself — that's the point.

## Development

```
python3 -m venv .venv
.venv/bin/pip install pytest
.venv/bin/python -m pytest session-archiver/scripts/tests/
```
