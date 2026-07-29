import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import backfill
from archive_lib import is_already_archived


def _make_transcript(path: Path, cwd: str, lines: int = 2):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        f.write(json.dumps({"role": "user", "cwd": cwd}) + "\n")
        for _ in range(lines - 1):
            f.write(json.dumps({"role": "assistant"}) + "\n")


def test_run_archives_new_sessions(tmp_path, monkeypatch):
    projects_root = tmp_path / "projects"
    archive_root = tmp_path / "archive"
    _make_transcript(
        projects_root / "-Users-foo-proj" / "sess-1.jsonl", "/Users/foo/proj"
    )

    monkeypatch.setattr(backfill, "PROJECTS_ROOT", projects_root)
    import archive_lib

    monkeypatch.setattr(archive_lib, "ARCHIVE_ROOT", archive_root)

    archived, skipped = backfill.run(force=False)

    assert archived == 1
    assert skipped == 0
    assert is_already_archived("sess-1", "/Users/foo/proj", archive_root=archive_root)


def test_run_skips_already_archived(tmp_path, monkeypatch):
    projects_root = tmp_path / "projects"
    archive_root = tmp_path / "archive"
    _make_transcript(
        projects_root / "-Users-foo-proj" / "sess-1.jsonl", "/Users/foo/proj"
    )

    monkeypatch.setattr(backfill, "PROJECTS_ROOT", projects_root)
    import archive_lib

    monkeypatch.setattr(archive_lib, "ARCHIVE_ROOT", archive_root)

    archived1, skipped1 = backfill.run(force=False)
    archived2, skipped2 = backfill.run(force=False)

    assert (archived1, skipped1) == (1, 0)
    assert (archived2, skipped2) == (0, 1)


def test_run_force_rearchives(tmp_path, monkeypatch):
    projects_root = tmp_path / "projects"
    archive_root = tmp_path / "archive"
    _make_transcript(
        projects_root / "-Users-foo-proj" / "sess-1.jsonl", "/Users/foo/proj"
    )

    monkeypatch.setattr(backfill, "PROJECTS_ROOT", projects_root)
    import archive_lib

    monkeypatch.setattr(archive_lib, "ARCHIVE_ROOT", archive_root)

    backfill.run(force=False)
    archived, skipped = backfill.run(force=True)

    assert archived == 1
    assert skipped == 0


def test_transcript_cwd_falls_back_to_dir_name(tmp_path):
    transcript = tmp_path / "-Users-foo-proj" / "sess-1.jsonl"
    transcript.parent.mkdir(parents=True)
    transcript.write_text(json.dumps({"role": "user"}) + "\n")

    assert backfill.transcript_cwd(transcript) == "-Users-foo-proj"
