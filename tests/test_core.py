import json
import os
from pathlib import Path

import pytest

from skill_diff import core
from skill_diff.core import SkillDiffError, compare, evidence, load, references, scan, validate

ROOT = Path(__file__).resolve().parents[1]


def skill(tmp_path, content="# Skill\n", **files):
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "SKILL.md").write_text(content, encoding="utf-8")
    for path, data in files.items():
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data if isinstance(data, bytes) else data.encode())
    return tmp_path


def test_demo_hidden_changes_and_reference_chain():
    a, b = scan(ROOT / "examples/before"), scan(ROOT / "examples/after")
    assert a["files"]["SKILL.md"] == b["files"]["SKILL.md"]
    report = compare(a, b)
    assert report["summary"]["changed_files"] == 3
    assert report["summary"]["added_signals"] == 4
    script = next(f for f in report["files"] if f["path"] == "scripts/summarize.py")
    assert script["route_after"] == ["SKILL.md", "references/workflow.md", "scripts/summarize.py"]
    assert not report["references_after"]["unresolved"]


def test_identical_snapshots_have_no_changes(tmp_path):
    snap = scan(skill(tmp_path))
    assert not compare(snap, snap)["changed"]


def test_prose_only_change_is_still_reviewable(tmp_path):
    root = skill(tmp_path)
    before = scan(root)
    (root / "SKILL.md").write_text("Do something entirely different.\n")
    report = compare(before, scan(root))
    assert report["changed"] and not report["signals"]


def test_binary_added_removed_and_unreferenced_files(tmp_path):
    root = skill(tmp_path, **{"image.bin": b"\x00\xff", "unused.txt": "old"})
    before = scan(root)
    (root / "image.bin").write_bytes(b"\x00\xfe")
    (root / "unused.txt").unlink()
    (root / "new.txt").write_text("new")
    report = compare(before, scan(root))
    assert {f["status"] for f in report["files"]} == {"modified", "removed", "added"}
    assert all(f["route_after"] is None for f in report["files"])


def test_snapshot_round_trip(tmp_path):
    snapshot = scan(skill(tmp_path / "skill", "中文\r\n"))
    path = tmp_path / "baseline.json"
    path.write_text(json.dumps(snapshot), encoding="utf-8")
    assert load(path) == snapshot


@pytest.mark.parametrize("mutation", [
    lambda x: x.update(schema="unknown"),
    lambda x: x.update(digest="0" * 64),
    lambda x: x["files"]["SKILL.md"].update(text="tampered"),
    lambda x: x["files"]["SKILL.md"].update(size=-1),
    lambda x: x["files"]["SKILL.md"].update(size=True),
    lambda x: x["files"].update({"../escape": x["files"]["SKILL.md"]}),
    lambda x: x["files"].update({"C:/escape": x["files"]["SKILL.md"]}),
    lambda x: x["files"]["SKILL.md"].update(text=None),
])
def test_invalid_snapshots_fail(tmp_path, mutation):
    snapshot = scan(skill(tmp_path))
    mutation(snapshot)
    with pytest.raises(SkillDiffError):
        validate(snapshot)


def test_missing_entrypoint(tmp_path):
    with pytest.raises(SkillDiffError, match="SKILL.md"):
        scan(tmp_path)


def test_invalid_utf8_entrypoint(tmp_path):
    (tmp_path / "SKILL.md").write_bytes(b"\xff")
    with pytest.raises(SkillDiffError, match="UTF-8"):
        scan(tmp_path)


def test_symlink_fails_instead_of_silently_skipping(tmp_path):
    root = skill(tmp_path / "skill")
    target = tmp_path / "outside.txt"
    target.write_text("outside")
    try:
        (root / "linked.txt").symlink_to(target)
    except OSError:
        pytest.skip("Symlink privilege unavailable on this Windows runner")
    with pytest.raises(SkillDiffError, match="Symlink"):
        scan(root)


def test_limits_fail_closed(tmp_path, monkeypatch):
    root = skill(tmp_path, "a" * 100)
    monkeypatch.setattr(core, "MAX_FILE", 10)
    with pytest.raises(SkillDiffError, match="limit"):
        scan(root)


def test_file_count_limit(tmp_path, monkeypatch):
    root = skill(tmp_path, **{"extra.txt": "x"})
    monkeypatch.setattr(core, "MAX_FILES", 1)
    with pytest.raises(SkillDiffError, match="limit"):
        scan(root)


def test_exclusions_are_only_documented_directories(tmp_path):
    root = skill(tmp_path, **{".git/config": "ignored", "__pycache__/x": "ignored", ".hidden": "tracked"})
    assert set(scan(root)["files"]) == {"SKILL.md", ".hidden"}


def test_graph_cycle_and_external_boundary(tmp_path):
    root = skill(tmp_path, "[next](references/a.md)\n[external](../secret.md)\n[missing](lost.md)\n", **{
        "references/a.md": "[root](../SKILL.md)\n`../scripts/run.py`\n",
        "scripts/run.py": "print('hello')",
    })
    graph = references(scan(root))
    assert graph["routes"]["scripts/run.py"] == ["SKILL.md", "references/a.md", "scripts/run.py"]
    assert {x["reason"] for x in graph["unresolved"]} == {"outside-skill", "missing"}


def test_reference_url_decoding_and_at_refs(tmp_path):
    root = skill(tmp_path, "[space](notes/a%20b.md#part)\n@notes/other.md\n", **{"notes/a b.md": "hello", "notes/other.md": "world"})
    # Percent-encoded whitespace is a valid Markdown path.
    graph = references(scan(root))
    assert "notes/other.md" in graph["routes"]
    assert "notes/a b.md" in graph["routes"]


def test_hosts_normalized_without_url_credentials(tmp_path):
    root = skill(tmp_path, "https://user:password@EXAMPLE.invalid:8443/path?q=token\n")
    signals = evidence(scan(root))
    assert signals[0]["value"] == "example.invalid:8443"


@pytest.mark.parametrize("declaration", ["Read Bash(git:*)", "[Read, Write]", "|\n  Read\n  Write", "\n  - Read\n  - Write"])
def test_tool_declarations_preserved(tmp_path, declaration):
    root = skill(tmp_path, "---\nname: sample\nallowed-tools: " + declaration + "\n---\n")
    signals = evidence(scan(root))
    assert len(signals) == 1 and signals[0]["kind"] == "tool-declaration"


def test_repeated_signal_lines_deduplicated(tmp_path):
    root = skill(tmp_path)
    before = scan(root)
    (root / "SKILL.md").write_text("https://a.invalid\nhttps://a.invalid\n")
    assert len(compare(before, scan(root))["signals"]) == 1


def test_line_moves_do_not_create_false_deltas(tmp_path):
    root = skill(tmp_path, "https://a.invalid\n")
    before = scan(root)
    (root / "SKILL.md").write_text("New heading\n\nhttps://a.invalid\n")
    report = compare(before, scan(root))
    assert report["changed"] and report["signals"] == []


def test_sensitive_path_boundaries(tmp_path):
    root = skill(tmp_path, "my.envvar environment .env.local ~/.ssh/id_rsa .aws/credentials\n")
    assert {x["value"] for x in evidence(scan(root))} == {".env.local", "~/.ssh/id_rsa", ".aws/credentials"}


def test_duplicate_snapshot_keys_fail(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text('{"schema":"skill-diff/snapshot-v1","schema":"other"}')
    with pytest.raises(SkillDiffError):
        load(path)


def test_snapshot_invalid_json_fails(tmp_path):
    path = tmp_path / "bad.json"
    path.write_bytes(b"not json")
    with pytest.raises(SkillDiffError, match="Invalid snapshot"):
        load(path)


def test_snapshot_digest_independent_of_root_and_creation_order(tmp_path):
    a = scan(skill(tmp_path / "a", "same", **{"z.txt": "last", "a.txt": "first"}))
    b = scan(skill(tmp_path / "b", "same", **{"a.txt": "first", "z.txt": "last"}))
    assert a == b
