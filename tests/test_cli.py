import json
import subprocess
import sys
from pathlib import Path

import pytest

from skill_diff.core import compare, scan
from skill_diff.render import html_report, markdown_report, text_report, md, diff_lines

ROOT = Path(__file__).resolve().parents[1]
BEFORE, AFTER = ROOT / "examples/before", ROOT / "examples/after"


def run(*args):
    return subprocess.run([sys.executable, "-m", "skill_diff", *map(str, args)], cwd=ROOT, capture_output=True, encoding="utf-8")


@pytest.mark.parametrize("fmt", ["text", "json", "markdown", "html"])
def test_diff_output_formats(fmt):
    result = run("diff", BEFORE, AFTER, "--format", fmt)
    assert result.returncode == 0 and "telemetry.example.invalid" in result.stdout
    if fmt == "json":
        assert json.loads(result.stdout)["summary"]["changed_files"] == 3


def test_check_gate_and_snapshot(tmp_path):
    snapshot = tmp_path / "baseline.json"
    assert run("snapshot", BEFORE, "-o", snapshot).returncode == 0
    assert run("check", snapshot, BEFORE).returncode == 0
    assert run("check", snapshot, AFTER).returncode == 1
    assert run("snapshot", BEFORE, "-o", snapshot).returncode == 2
    assert run("snapshot", BEFORE, "-o", snapshot, "--force").returncode == 0


@pytest.mark.parametrize("policy,code", [("none", 0), ("change", 1), ("signals", 1), ("high", 1)])
def test_exit_policies(policy, code):
    assert run("diff", BEFORE, AFTER, "--fail-on", policy).returncode == code


def test_output_written_even_when_gate_fails(tmp_path):
    report = tmp_path / "report.html"
    assert run("check", BEFORE, AFTER, "--format", "html", "-o", report).returncode == 1
    assert report.read_text(encoding="utf-8").startswith("<!doctype html>")


def test_missing_input_is_error(tmp_path):
    result = run("diff", tmp_path / "missing", AFTER)
    assert result.returncode == 2 and "Traceback" not in result.stderr


def test_invalid_snapshot_is_error(tmp_path):
    invalid = tmp_path / "bad.json"
    invalid.write_text('{"schema":"unknown"}')
    result = run("check", invalid, AFTER)
    assert result.returncode == 2 and not result.stdout


def test_output_cannot_overwrite_inputs(tmp_path):
    assert run("diff", BEFORE, AFTER, "-o", AFTER / "SKILL.md").returncode == 2
    path = tmp_path / "baseline.json"
    assert run("snapshot", BEFORE, "-o", path).returncode == 0
    assert run("diff", path, AFTER, "-o", path).returncode == 2


def test_renderers_escape_untrusted_content(tmp_path):
    (tmp_path / "SKILL.md").write_text("before")
    before = scan(tmp_path)
    payload = '<script>alert(1)</script>\x1b[31m\u202ehidden\nhttps://bad.invalid/\n'
    (tmp_path / "SKILL.md").write_text(payload, encoding="utf-8")
    report = compare(before, scan(tmp_path))
    output = html_report(report)
    assert "<script>" not in output and "&lt;script&gt;" in output
    assert "default-src 'none'" in output
    assert "\x1b" not in text_report(report) and "\u202e" not in text_report(report)
    assert "<script>" not in markdown_report(report)


def test_binary_report(tmp_path):
    (tmp_path / "SKILL.md").write_text("demo")
    before = scan(tmp_path)
    (tmp_path / "asset.bin").write_bytes(b"\x00\xff")
    assert "Binary or non-UTF-8" in html_report(compare(before, scan(tmp_path)))


def test_prose_gate_blocks_without_matching_signals(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir()
    b.mkdir()
    (a / "SKILL.md").write_text("Before")
    (b / "SKILL.md").write_text("After")
    assert run("check", a, b).returncode == 1
    assert run("check", a, b, "--fail-on", "signals").returncode == 0


def test_markdown_cannot_embed_external_images_or_links():
    output = md("![private](https://outside.invalid/image) | <img src=x>")
    assert "![" not in output and "](" not in output and "<img" not in output
    assert "|" not in output


def test_large_preview_is_explicitly_omitted():
    rows, note = diff_lines({"path": "large.md", "before": None,
                             "after": {"text": "x" * 200_001}})
    assert rows == [] and "omitted" in note


def test_final_newline_changes_are_not_hidden():
    rows, note = diff_lines({"path": "SKILL.md", "before": {"text": "a\n"}, "after": {"text": "a"}})
    assert rows == [] and "newline" in note
