import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from archive_lib import (
    build_archive_record,
    encode_project_path,
    is_already_archived,
    write_archive_record,
)


def test_encode_project_path_replaces_non_alphanumeric():
    assert encode_project_path("/Users/foo/bar-baz") == "-Users-foo-bar-baz"


def test_build_archive_record_preserves_raw_turns(tmp_path):
    transcript = tmp_path / "session.jsonl"
    transcript.write_text('{"role": "user", "isMeta": true}\n{"role": "assistant"}\n')

    record = build_archive_record("sess-1", "/Users/foo/proj", str(transcript))

    assert record["schema_version"] == 1
    assert record["session_id"] == "sess-1"
    assert record["project_path"] == "/Users/foo/proj"
    assert record["source_transcript_path"] == str(transcript)
    assert record["turns"] == [{"role": "user", "isMeta": True}, {"role": "assistant"}]
    assert "archived_at" in record


def test_write_archive_record_writes_expected_path(tmp_path):
    record = {
        "schema_version": 1,
        "session_id": "sess-1",
        "project_path": "/Users/foo/proj",
        "archived_at": "now",
        "source_transcript_path": "x",
        "turns": [],
    }

    out_path = write_archive_record(record, archive_root=tmp_path)

    assert out_path == tmp_path / "-Users-foo-proj" / "sess-1.json"
    assert json.loads(out_path.read_text()) == record


def test_write_archive_record_is_idempotent_overwrite(tmp_path):
    record = {
        "schema_version": 1,
        "session_id": "sess-1",
        "project_path": "/proj",
        "archived_at": "t1",
        "source_transcript_path": "x",
        "turns": [],
    }
    write_archive_record(record, archive_root=tmp_path)
    record["archived_at"] = "t2"
    out_path = write_archive_record(record, archive_root=tmp_path)

    assert json.loads(out_path.read_text())["archived_at"] == "t2"


def test_is_already_archived(tmp_path):
    assert not is_already_archived("sess-1", "/proj", archive_root=tmp_path)
    write_archive_record(
        {
            "schema_version": 1,
            "session_id": "sess-1",
            "project_path": "/proj",
            "archived_at": "t1",
            "source_transcript_path": "x",
            "turns": [],
        },
        archive_root=tmp_path,
    )
    assert is_already_archived("sess-1", "/proj", archive_root=tmp_path)
