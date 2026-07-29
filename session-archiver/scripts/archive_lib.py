#!/usr/bin/env python3
"""Shared normalization logic for archive_session.py and backfill.py."""
import json
import re
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = 2
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


def _iter_tool_result_hashes(turns: list):
    """Find tool-results/<hash>.txt references inside a turn's content blocks."""
    for turn in turns:
        content = turn.get("message", {}).get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            for value in block.values():
                if isinstance(value, str):
                    for match in re.finditer(r"tool-results/([A-Za-z0-9]+)\.txt", value):
                        yield match.group(1)


def read_subagents(session_dir: Path) -> list:
    subagents = []
    for transcript_path in sorted(session_dir.glob("subagents/agent-*.jsonl")):
        agent_id = transcript_path.stem[len("agent-"):]
        meta_path = transcript_path.with_suffix(".meta.json")
        meta = json.loads(meta_path.read_text()) if meta_path.exists() else None
        subagents.append({
            "agent_id": agent_id,
            "meta": meta,
            "turns": read_turns(str(transcript_path)),
        })
    return subagents


def read_tool_results(session_dir: Path, referenced_hashes: set) -> dict:
    tool_results = {}
    results_dir = session_dir / "tool-results"
    if not results_dir.is_dir():
        return tool_results
    for hash_ in referenced_hashes:
        result_path = results_dir / f"{hash_}.txt"
        if result_path.exists():
            tool_results[hash_] = result_path.read_text(encoding="utf-8")
    return tool_results


def build_archive_record(session_id: str, project_path: str, transcript_path: str) -> dict:
    session_dir = Path(transcript_path).parent
    turns = read_turns(transcript_path)
    subagents = read_subagents(session_dir)

    referenced_hashes = set(_iter_tool_result_hashes(turns))
    for subagent in subagents:
        referenced_hashes.update(_iter_tool_result_hashes(subagent["turns"]))

    return {
        "schema_version": SCHEMA_VERSION,
        "session_id": session_id,
        "project_path": project_path,
        "archived_at": datetime.now(timezone.utc).isoformat(),
        "source_transcript_path": transcript_path,
        "turns": turns,
        "subagents": subagents,
        "tool_results": read_tool_results(session_dir, referenced_hashes),
    }


def write_archive_record(record: dict, archive_root: Path = ARCHIVE_ROOT) -> Path:
    project_dir = archive_root / encode_project_path(record["project_path"])
    project_dir.mkdir(parents=True, exist_ok=True)
    out_path = project_dir / f"{record['session_id']}.json"
    out_path.write_text(json.dumps(record, indent=2))
    return out_path


def is_already_archived(session_id: str, project_path: str, archive_root: Path = ARCHIVE_ROOT) -> bool:
    project_dir = archive_root / encode_project_path(project_path)
    return (project_dir / f"{session_id}.json").exists()
