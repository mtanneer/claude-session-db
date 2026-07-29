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
  "schema_version": 1,
  "session_id": "...",
  "project_path": "...",
  "archived_at": "2026-07-22T...",
  "source_transcript_path": "~/.claude/projects/.../<id>.jsonl",
  "turns": [ /* raw transcript lines, as-is */ ]
}
```

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
