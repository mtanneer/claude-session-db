# claude-session-db — a durable, indexed copy of Claude Code session data

## Context

Built as a split-out from the `sediment` plugin project
(`frameworks.plugins.claude.sediment`). While building Sediment's
friction-mining pipeline, real testing traced a concrete architectural
gap: Claude Code has no durable, indexed session store.
`~/.claude/history.jsonl` (prompt-only, never pruned) and
`~/.claude/projects/<encoded>/<session-id>.jsonl` (full transcript,
auto-deleted after 30 days via `cleanupPeriodDays`) are two independent,
unsynchronized logs with no reconciliation. Sediment's `friction-miner`
had to work around this (a skip-on-missing-file fix in
`heuristic_filter.py`) rather than being insulated from it — on one real
machine, 166 of 240 session IDs `history.jsonl` still remembered had
already lost their transcript file.

Researching GitHub Copilot's Chronicle feature showed the alternative:
a first-party incrementally-built local index (SQLite) plus optional
durable sync, decoupling the query layer from the raw, mutable/pruned
source logs entirely. The vision here: build the Claude Code equivalent
— not by copying Chronicle's specific tech, but by giving Sediment (and
future tools) a durable, stable-schema copy that isn't subject to Claude
Code's own retention policy, isn't at risk of internal schema drift
breaking downstream parsers, and is built incrementally as sessions
happen rather than reconstructed after the fact.

Confirmed via research (and empirically, after an initial failed attempt):
Claude Code's `dependencies` field in `plugin.json` is real and enforced,
not just documentation — but auto-install only works same-marketplace
with the bare-string form (`"dependencies": ["session-archiver"]`).
Since `session-archiver` and `sediment` live in separate repos/
marketplaces, cross-marketplace resolution requires the object form
(`{ "name": "session-archiver", "marketplace": "claude-session-db" }`)
in the dependent's `plugin.json`, AND an
`"allowCrossMarketplaceDependenciesOn": ["claude-session-db"]` entry in
the *root* marketplace hosting the dependent plugin (`sediment-dev`'s
`marketplace.json`). Both marketplaces still need `marketplace add` run
first — installing a dependency doesn't auto-add its marketplace. This
is the "bundled like a pip package" mechanism Sediment uses to depend on
this project.

## Prior-art check (done before committing to build this)

Before designing a new archiver, researched existing tools rather than
assuming nothing exists:

- **DazzleML/Claude-Session-Backup** — real Claude Code plugin
  (`.claude-plugin/plugin.json` + `marketplace.json`), actively
  maintained (daily commits), git-backed storage with a rebuildable
  SQLite index and real deletion detection. Looked initially like a
  strong build-vs-buy case. **Disqualified on inspection of its actual
  source** (`transcript_walker.py`, `fts5_db.py`, `index.py` read via
  `gh api`): licensed GPL-3.0 (real dependency-licensing conflict, not
  a style preference), and its schema deliberately collapses
  `attributionSkill` into a coarse `role_subtype` bucket while never
  capturing `isMeta`, `attributionPlugin`, or `origin.kind` at all — it
  preserves turn content "VERBATIM, no stripping" for full-text search/
  recovery, not for provenance filtering. It cannot answer the specific
  question Sediment's `_is_human_turn()` needs answered. Depending on it
  would mean taking on a GPL dependency and a heavy external data store
  while still having to write our own provenance parser on top anyway.
- **neonplants/claude-code-session-archiver** — skill-based (manual
  "end session" trigger), not hook-driven, and stores Markdown rather
  than structured/parseable data. Wrong invocation model (contradicts
  the confirmed `SessionEnd`-hook requirement) and wrong output shape
  for automated parsing.

Neither fits. Building this ourselves is the confirmed right call, not
a default reached by skipping the search.

## What this is

**`claude-session-db`** (plugin name: `session-archiver`) — a Claude
Code plugin that:
1. Registers a `SessionEnd` hook to copy+normalize each session's
   transcript into a durable archive at `~/.claude-archive/` the moment
   a session ends (going forward).
2. Ships a one-time backfill command to archive every transcript that
   still exists on disk today, before more age out under the 30-day
   default retention.
3. Exposes the normalized archive as a stable read source other tools
   (Sediment, and anything built later) can depend on instead of
   reading `~/.claude/projects/` directly.

Sediment (separate repo, `frameworks.plugins.claude.sediment`) will
declare `"dependencies": ["session-archiver"]` in its own
`plugin.json` once this project is usable, and switch
`discover_sessions.py`/`heuristic_filter.py` to read from
`~/.claude-archive/` instead of raw transcripts — that integration work
happens in Sediment's repo, as a follow-up, not here.

## Scope for this pass

- **Location**: `~/.claude-archive/` — outside `~/.claude` entirely, so
  it's unambiguously separate from anything Claude Code's own retention
  logic could ever touch.
- **Capture going forward**: `SessionEnd` hook, using the confirmed real
  payload (`transcript_path`, `session_id`, `cwd`, `reason`,
  `hook_event_name`). Hook is fire-and-forget per Claude Code's own docs
  (SessionEnd "is a terminal event—it cannot be blocked... exit codes
  and JSON output are ignored") — the archiver script must be
  best-effort, never assume its failure is visible to the user
  in-session.
- **Capturing the past**: one-time backfill of whatever transcripts
  still exist on disk *right now*. Explicitly NOT attempting to
  reconstruct already-pruned sessions from `history.jsonl`'s prompt-only
  log — no assistant responses/tool calls survive there, so there's
  nothing to mine; accepted as a real, permanent loss rather than
  building a lower-fidelity fallback.
- **Format**: thin normalization, not raw copy, not curated extraction.
  Every turn's fields (role, content, `isMeta`, `attributionSkill`,
  `attributionPlugin`, `origin`, tool_use blocks, timestamps — every key
  present in the raw transcript) preserved under a stable top-level
  structure. Guarantees consistent access patterns without discarding
  anything a future heuristic might need — critical given Sediment's own
  experience needing `isMeta`/`attributionSkill` fields that weren't
  anticipated when its heuristic filter was first built.

## Architecture

```
frameworks.plugins.claude-session-db/   (this repo)
├── .claude-plugin/
│   └── marketplace.json                (lists the session-archiver plugin)
├── plans/
│   └── PLAN.md                         (this file)
└── session-archiver/
    ├── .claude-plugin/
    │   └── plugin.json
    ├── hooks/
    │   └── hooks.json                  (SessionEnd -> archive_session.py)
    ├── commands/
    │   └── backfill-archive.md         (/session-archiver:backfill-archive)
    ├── scripts/
    │   ├── archive_session.py          (hook entrypoint: normalize + write one session)
    │   ├── backfill.py                 (one-time: archive every transcript found on disk today)
    │   └── tests/
    │       ├── test_archive_session.py
    │       └── test_backfill.py
    └── README.md
```

### Normalized schema (per session file, `~/.claude-archive/<project-encoded>/<session-id>.json`)

```json
{
  "schema_version": 1,
  "session_id": "...",
  "project_path": "...",
  "archived_at": "2026-07-22T...",
  "source_transcript_path": "~/.claude/projects/.../<id>.jsonl",
  "turns": [
    { /* the raw parsed JSON object for this line, untouched */ }
  ]
}
```
`schema_version` exists from day one so future format changes to the
archive itself (not Claude Code's format — this project's own) can be
detected and migrated, without guessing. `turns` holds each raw
transcript line as-is (already valid JSON per Claude Code's own JSONL
format) — "thin normalization" means wrapping with stable metadata, not
reinterpreting turn contents.

### `archive_session.py` (hook entrypoint)

Reads the SessionEnd payload from stdin (confirmed: `session_id`,
`transcript_path`, `cwd`, `reason`, `hook_event_name`). Reads
`transcript_path`, wraps its lines into the schema above, writes to
`~/.claude-archive/<encoded-project>/<session-id>.json`. Idempotent
(overwrite-safe) so re-running on the same session is harmless. Must
never throw uncaught — wrap the whole body in try/except and exit 0
regardless, since SessionEnd's exit code is ignored anyway and a crash
here must never be visible as a Claude Code error to the user.

Encoding project path: reuse the exact same non-alphanumeric-to-`-`
scheme Claude Code itself uses for `~/.claude/projects/<encoded>/`
(confirmed via docs) — consistent naming, though that encoding is known
lossy for hyphenated directories (collides — see
anthropics/claude-code#7009, #21085), so `project_path` is stored
uncorrupted in the JSON body as the authoritative value; the directory
name is just a convenient bucket, never looked up by decoding it.

### `backfill.py` (one-time capture of what's on disk today)

Walks `~/.claude/projects/*/*.jsonl` directly (every transcript that
currently exists — this is the "past-recoverable" set, full stop), runs
each through the same normalization as `archive_session.py`, writes to
the archive. Skips (doesn't re-archive) any session_id already present
in `~/.claude-archive/` unless a `--force` flag is passed. Prints a
summary: sessions archived, sessions skipped (already archived).

### `hooks/hooks.json`

```json
{
  "hooks": {
    "SessionEnd": [
      {
        "matcher": "*",
        "hooks": [{ "type": "command", "command": "${CLAUDE_PLUGIN_DIR}/scripts/archive_session.py" }]
      }
    ]
  }
}
```
(Exact matcher value / plugin-dir variable to be confirmed against real
hooks.json examples in installed plugins during implementation — not
guessed at plan time.)

## Verification

- Unit tests (pytest) for `archive_session.py`'s normalization logic
  and `backfill.py`'s skip-already-archived behavior — both
  pure-function-testable, same pattern Sediment's own script tests use.
- Manually trigger a real `SessionEnd` (end a real Claude Code session)
  and confirm a file appears under `~/.claude-archive/` with the
  expected schema, sourced from that session's real `transcript_path`.
- Run `/session-archiver:backfill-archive` for real and confirm the
  archive count matches the number of transcripts actually present
  under `~/.claude/projects/` at run time.
- Once Sediment depends on this (follow-up, in Sediment's repo):
  re-point its scripts at the archive and re-run a known scan,
  confirming identical candidate output to prove the switch from
  raw-transcript reading to archive reading is behavior-preserving.
- Confirm a plugin that declares `"dependencies": ["session-archiver"]`
  actually triggers auto-install: test via a fresh
  `/plugin marketplace add` + `/plugin install` cycle and observe both
  plugins land.

## Explicitly not doing (this pass)

- No reconstruction of already-pruned sessions from `history.jsonl` —
  confirmed accepted loss.
- No cloud/cross-machine sync (Copilot Chronicle's optional server-side
  piece) — purely local, single-machine archive for now.
- No SQLite/database index — flat normalized JSON files per session,
  matching "thin normalization," not a queryable store. If query
  performance ever becomes a problem at large archive scale, that's a
  future pass, not blocking this one. (Despite the repo name
  `claude-session-db`, the first working version is flat files — the
  name reflects the eventual destination, not a commitment to build a
  real database on day one.)
- No changes to Sediment's own scripts — that integration (switching
  `discover_sessions.py`/`heuristic_filter.py` to read from the
  archive, adding the `dependencies` declaration) happens in Sediment's
  repo as a separate follow-up once this plugin is working and
  published.
- No archive retention/cleanup policy of its own — the whole point is
  this store doesn't get pruned; revisit only if disk usage becomes a
  real complaint.
