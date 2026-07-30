# Claude Session DB

![version](https://img.shields.io/badge/dynamic/json?url=https://raw.githubusercontent.com/mtanneer/claude-session-db/main/session-archiver/.claude-plugin/plugin.json&query=%24.version&label=version)

A Claude Code plugin marketplace hosting **session-archiver**: a durable,
outside-the-retention-policy archive of your Claude Code session
transcripts.

Claude Code keeps two logs and neither is a safe long-term source:
`~/.claude/history.jsonl` is a prompt-only index that's never pruned, and
`~/.claude/projects/<encoded>/<session-id>.jsonl` has the full transcript
but gets deleted after `cleanupPeriodDays` (30 days by default). The two
aren't reconciled with each other — on one real machine, 166 of 240
session IDs still listed in `history.jsonl` had already lost their
transcript file. session-archiver closes that gap: a `SessionEnd` hook
copies+normalizes every session into `~/.claude-archive/` the moment it
ends, plus a one-time backfill command for everything still on disk today.

## Install

```
/plugin marketplace add mtanneer/claude-session-db
/plugin install session-archiver
```

Then, to capture every transcript currently on disk before more age out:

```
/session-archiver:backfill-archive
```

Going forward, every session is archived automatically on `SessionEnd` —
no further action needed.

## What you get

One JSON file per session, forever, at
`~/.claude-archive/<encoded-project-path>/<session-id>.json`:

```json
{
  "schema_version": 1,
  "session_id": "...",
  "project_path": "...",
  "archived_at": "2026-07-22T...",
  "source_transcript_path": "~/.claude/projects/.../<id>.jsonl",
  "turns": [ /* every raw transcript line, untouched */ ]
}
```

"Thin normalization": every field of every turn (`role`, `content`,
`isMeta`, `attributionSkill`, `attributionPlugin`, `origin`, tool calls,
timestamps) is preserved exactly as Claude Code wrote it — wrapped with
stable metadata, never reinterpreted. `schema_version` exists so future
changes to *this archive's* format can be detected and migrated.

## Non-goals

- **No reconstruction of already-pruned sessions.** `history.jsonl` is
  prompt-only — no assistant turns survive there, so there's nothing to
  mine. That loss is accepted as permanent, not patched over with a
  lower-fidelity fallback.
- **No cloud sync.** Purely local, single-machine.
- **No SQLite index, no query layer.** Flat JSON files per session. If
  query performance ever becomes a real problem at scale, that's a future
  pass — not a day-one commitment. (The repo name is aspirational; the
  first working version is flat files.)
- **No retention or cleanup of its own.** Permanence outside Claude Code's
  retention policy is the entire point.

## For plugin authors

The archive is meant as a stable read source other plugins can depend on
instead of parsing `~/.claude/projects/` directly. Declare a
cross-marketplace dependency in your own `plugin.json`:

```json
{
  "dependencies": [
    { "name": "session-archiver", "marketplace": "claude-session-db", "version": "^1.0.0" }
  ]
}
```

...and add `"allowCrossMarketplaceDependenciesOn": ["claude-session-db"]`
to your own marketplace's `marketplace.json`. Both marketplaces still need
`/plugin marketplace add` run once — declaring the dependency doesn't
auto-add its marketplace. [Sediment](https://github.com/mtanneer/sediment)
uses exactly this mechanism.

## Development

See [CONTRIBUTING.md](CONTRIBUTING.md) for setup, test commands, and PR
conventions.

## Architecture

```
session-archiver/
├── .claude-plugin/plugin.json      # plugin manifest
├── hooks/hooks.json                # SessionEnd -> archive_session.py
├── commands/backfill-archive.md    # /session-archiver:backfill-archive
├── scripts/
│   ├── archive_lib.py              # shared normalization: build/write/check archive records
│   ├── archive_session.py          # SessionEnd hook entrypoint
│   ├── backfill.py                 # one-time: archive every transcript found on disk today
│   └── tests/
└── README.md
```

See [`plans/PLAN.md`](plans/PLAN.md) for the full design rationale,
including a prior-art comparison against two existing archiver tools
(both disqualified — GPL licensing and wrong invocation model,
respectively) and the origin story: this was split out of
[Sediment](https://github.com/mtanneer/sediment) after it hit real gaps
from having no durable session store.
