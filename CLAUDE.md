# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

**`claude-session-db`** (plugin name: `session-archiver`) — a Claude Code
plugin that archives session transcripts into a durable, normalized local
store at `~/.claude-archive/`, outside Claude Code's own retention policy
(`~/.claude/projects/` transcripts are auto-deleted after `cleanupPeriodDays`,
default 30 days).

It registers a `SessionEnd` hook that archives each session the moment it
ends, plus a one-time `/session-archiver:backfill-archive` command to
archive every transcript still on disk before more age out. The archive is
meant as a stable read source other plugins can depend on instead of
reading `~/.claude/projects/` directly — see `plans/PLAN.md` for the full
design rationale, including a prior-art comparison against two existing
archiver tools (both disqualified — see plan for why) and the origin story
(split out of the `sediment` plugin, which hit real gaps from having no
durable session store).

## Commands

```
python3 -m venv .venv
.venv/bin/pip install pytest
.venv/bin/python -m pytest session-archiver/scripts/tests/
```

Single test: `.venv/bin/python -m pytest session-archiver/scripts/tests/test_archive_session.py -v`

## Architecture

```
session-archiver/
├── .claude-plugin/plugin.json      # plugin manifest
├── hooks/hooks.json                # SessionEnd -> archive_session.py
├── commands/backfill-archive.md    # /session-archiver:backfill-archive
├── scripts/
│   ├── archive_lib.py              # shared normalization: build/write/check archive records
│   ├── archive_session.py          # SessionEnd hook entrypoint (reads payload from stdin)
│   ├── backfill.py                 # one-time: archive every transcript found on disk today
│   └── tests/
└── README.md
```

Normalized archive record, one JSON file per session at
`~/.claude-archive/<encoded-project-path>/<session-id>.json`:

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

`turns` preserves every field of every transcript line untouched
("thin normalization" — wrap with stable metadata, never reinterpret
turn content). `schema_version` exists so future changes to *this
archive's* format (not Claude Code's) can be detected and migrated.
`v2` adds `subagents` (Task-tool runs, normally written to a sibling
`subagents/agent-<agentId>.jsonl` and never inlined into the main
transcript) and `tool_results` (large tool outputs Claude Code offloads
to `tool-results/<hash>.txt`, referenced by hash rather than inlined) —
both previously excluded, so a "full transcript" archive still had gaps
for delegated-agent work and large tool output. `v1` archives predate
both fields; their absence there means "not captured," not "empty."

Project-path encoding mirrors Claude Code's own `~/.claude/projects/<encoded>/`
scheme (non-alphanumeric → `-`), but that scheme is known-lossy for
hyphenated paths (collides — see anthropics/claude-code#7009, #21085).
The directory is only ever used as a bucket, never decoded back — the
authoritative `project_path` is stored uncorrupted inside the JSON body
itself (`encode_project_path` in `archive_lib.py`).

## Hard constraints

- `archive_session.py` is a `SessionEnd` hook entrypoint. SessionEnd is a
  terminal, unblockable event whose exit code Claude Code ignores — the
  script must never raise; any failure here is invisible to the user by
  design (see the module docstring and its bare `except Exception: pass`).
- No reconstruction of already-pruned sessions from `history.jsonl` —
  it's prompt-only, no assistant turns survive there, so there's nothing
  to mine. Treated as permanent, accepted loss, not something to work
  around with a lower-fidelity fallback.
- No cloud sync, no SQLite index, no retention/cleanup of the archive
  itself — flat JSON files per session, kept forever. That permanence
  outside Claude Code's own retention policy is the entire point of this
  project.

## Relationship to `sediment`

Sediment (sibling repo, `frameworks.plugins.claude.sediment`) is meant to
eventually declare `"dependencies": ["session-archiver"]` in its own
`plugin.json` and read from `~/.claude-archive/` instead of raw
transcripts directly — that integration is out of scope here and happens
in Sediment's own repo.
