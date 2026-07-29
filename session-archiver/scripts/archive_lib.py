#!/usr/bin/env python3
"""Shared normalization logic for archive_session.py and backfill.py."""

import json
import re
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = 1
ARCHIVE_ROOT = Path.home() / ".claude-archive"


def encode_project_path(cwd: str) -> str:
    """Mirror Claude Code's own ~/.claude/projects/<encoded> naming scheme.

    Known-lossy for hyphenated paths (see anthropics/claude-code#7009,
    #21085) — only used as a directory bucket, never decoded back.
    """
    return re.sub(r"[^A-Za-z0-9]", "-", cwd)


def read_turns(transcript_path: str) -> list:
    turns = []
    with open(transcript_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                turns.append(json.loads(line))
    return turns


def build_archive_record(
    session_id: str, project_path: str, transcript_path: str
) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "session_id": session_id,
        "project_path": project_path,
        "archived_at": datetime.now(timezone.utc).isoformat(),
        "source_transcript_path": transcript_path,
        "turns": read_turns(transcript_path),
    }


def write_archive_record(record: dict, archive_root: Path = ARCHIVE_ROOT) -> Path:
    project_dir = archive_root / encode_project_path(record["project_path"])
    project_dir.mkdir(parents=True, exist_ok=True)
    out_path = project_dir / f"{record['session_id']}.json"
    out_path.write_text(json.dumps(record, indent=2))
    return out_path


def is_already_archived(
    session_id: str, project_path: str, archive_root: Path = ARCHIVE_ROOT
) -> bool:
    project_dir = archive_root / encode_project_path(project_path)
    return (project_dir / f"{session_id}.json").exists()
