#!/usr/bin/env python3
"""SessionEnd hook entrypoint. Reads the hook payload from stdin, archives
the session's transcript. SessionEnd is a terminal, unblockable event whose
exit code Claude Code ignores — this must never raise, so any failure here
stays invisible to the user rather than surfacing as a Claude Code error.
"""
import json
import sys

from archive_lib import build_archive_record, write_archive_record


def main():
    try:
        payload = json.load(sys.stdin)
        record = build_archive_record(
            session_id=payload["session_id"],
            project_path=payload["cwd"],
            transcript_path=payload["transcript_path"],
        )
        write_archive_record(record)
    except Exception:
        pass


if __name__ == "__main__":
    main()
