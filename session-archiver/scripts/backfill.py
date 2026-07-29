#!/usr/bin/env python3
"""One-time backfill: archive every transcript still on disk under
~/.claude/projects/*/*.jsonl before it ages out under the 30-day
cleanupPeriodDays default. Skips sessions already archived unless --force.
"""
import argparse
import json
import sys
from pathlib import Path

import archive_lib
from archive_lib import build_archive_record, is_already_archived, write_archive_record

PROJECTS_ROOT = Path.home() / ".claude" / "projects"


def transcript_cwd(transcript_path: Path) -> str:
    with open(transcript_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            cwd = json.loads(line).get("cwd")
            if cwd:
                return cwd
            break
    # ponytail: no cwd on first line, fall back to the (lossy) encoded dir name
    return transcript_path.parent.name


def run(force: bool) -> tuple[int, int]:
    archive_root = archive_lib.ARCHIVE_ROOT
    archived, skipped = 0, 0
    for transcript_path in sorted(PROJECTS_ROOT.glob("*/*.jsonl")):
        session_id = transcript_path.stem
        project_path = transcript_cwd(transcript_path)
        if not force and is_already_archived(session_id, project_path, archive_root=archive_root):
            skipped += 1
            continue
        record = build_archive_record(session_id, project_path, str(transcript_path))
        write_archive_record(record, archive_root=archive_root)
        archived += 1
    return archived, skipped


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="Re-archive sessions that already exist in the archive")
    args = parser.parse_args()

    archived, skipped = run(args.force)
    print(f"Archived: {archived}, skipped (already archived): {skipped}")


if __name__ == "__main__":
    main()
