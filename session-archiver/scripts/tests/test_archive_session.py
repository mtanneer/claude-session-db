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

    assert record["schema_version"] == 2
    assert record["session_id"] == "sess-1"
    assert record["project_path"] == "/Users/foo/proj"
    assert record["source_transcript_path"] == str(transcript)
    assert record["turns"] == [{"role": "user", "isMeta": True}, {"role": "assistant"}]
    assert record["subagents"] == []
    assert record["tool_results"] == {}
    assert "archived_at" in record


def test_build_archive_record_includes_subagents_and_tool_results(tmp_path):
    session_dir = tmp_path
    transcript = session_dir / "session.jsonl"
    transcript.write_text(
        json.dumps({"message": {"content": [{"text": "see tool-results/abc123.txt"}]}})
        + "\n"
    )

    subagents_dir = session_dir / "subagents"
    subagents_dir.mkdir()
    (subagents_dir / "agent-xyz.jsonl").write_text(
        json.dumps({"message": {"content": [{"text": "hi"}]}}) + "\n"
    )
    (subagents_dir / "agent-xyz.meta.json").write_text(
        json.dumps({"agentType": "Explore", "description": "test agent"})
    )

    results_dir = session_dir / "tool-results"
    results_dir.mkdir()
    (results_dir / "abc123.txt").write_text("big tool output")
    (results_dir / "unreferenced.txt").write_text("should not be archived")

    record = build_archive_record("sess-1", "/Users/foo/proj", str(transcript))

    assert len(record["subagents"]) == 1
    assert record["subagents"][0]["agent_id"] == "xyz"
    assert record["subagents"][0]["meta"] == {
        "agentType": "Explore",
        "description": "test agent",
    }
    assert record["subagents"][0]["turns"] == [
        {"message": {"content": [{"text": "hi"}]}}
    ]

    assert record["tool_results"] == {"abc123": "big tool output"}


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
