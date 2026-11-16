"""Bounded filesystem snapshots and deterministic, evidence-based comparisons.

Nothing in a skill is imported, executed or fetched. Text is data throughout.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from collections import deque
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlsplit

SCHEMA = "skill-diff/snapshot-v1"
MAX_FILE = 8 * 1024 * 1024
MAX_TOTAL = 64 * 1024 * 1024
MAX_FILES = 5000
MAX_SNAPSHOT = 128 * 1024 * 1024
EXCLUDED = {".git", "__pycache__"}


class SkillDiffError(ValueError):
    """An input could not be reviewed completely."""


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def digest(files: dict) -> str:
    # JSON frames names, hashes and sizes unambiguously; no machine-specific paths.
    rows = [[p, f["sha256"], f["size"]] for p, f in sorted(files.items())]
    return sha(json.dumps(rows, ensure_ascii=True, separators=(",", ":")).encode())


def _linked(path: Path) -> bool:
    info = path.lstat()
    return stat.S_ISLNK(info.st_mode) or bool(
        getattr(info, "st_file_attributes", 0) & 0x400  # Windows reparse points
    )


def scan(directory: str | Path) -> dict:
    root = Path(directory).expanduser().resolve()
    if not root.is_dir() or not (root / "SKILL.md").is_file():
        raise SkillDiffError(f"Expected one skill directory containing SKILL.md: {root}")
    files: dict = {}
    total = 0
    for current, dirs, names in os.walk(root, followlinks=False, onerror=lambda e: (_ for _ in ()).throw(e)):
        dirs[:] = sorted(d for d in dirs if d not in EXCLUDED)
        for name in dirs + sorted(names):
            path = Path(current) / name
            if _linked(path):
                raise SkillDiffError(f"Symlink or reparse point is not supported: {path.relative_to(root)}")
        for name in sorted(names):
            path = Path(current) / name
            rel = path.relative_to(root).as_posix()
            info = path.stat()
            if not stat.S_ISREG(info.st_mode):
                raise SkillDiffError(f"Not a regular file: {rel}")
            if info.st_size > MAX_FILE or total + info.st_size > MAX_TOTAL or len(files) >= MAX_FILES:
                raise SkillDiffError(f"Scan limit exceeded at {rel}; no partial report produced")
            # Bounded read also handles files that grew after stat().
            with path.open("rb") as stream:
                data = stream.read(MAX_FILE + 1)
            total += len(data)
            if len(data) > MAX_FILE or total > MAX_TOTAL:
                raise SkillDiffError(f"Scan limit exceeded at {rel}")
            try:
                text = data.decode("utf-8") if b"\0" not in data else None
            except UnicodeDecodeError:
                text = None
            files[rel] = {"sha256": sha(data), "size": len(data), "text": text}
    if "SKILL.md" not in files:
        raise SkillDiffError("The entrypoint filename must be exactly SKILL.md (case-sensitive)")
    if files["SKILL.md"]["text"] is None:
        raise SkillDiffError("SKILL.md must be UTF-8 text")
    return {"schema": SCHEMA, "digest": digest(files), "files": files}


def load(source: str | Path) -> dict:
    path = Path(source).expanduser()
    if path.is_dir():
        return scan(path)
    with path.open("rb") as stream:
        raw = stream.read(MAX_SNAPSHOT + 1)
    if len(raw) > MAX_SNAPSHOT:
        raise SkillDiffError("Snapshot exceeds size limit")
    try:
        def unique_pairs(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise SkillDiffError(f"Duplicate snapshot key: {key}")
                result[key] = value
            return result
        obj = json.loads(raw, object_pairs_hook=unique_pairs)
    except (ValueError, UnicodeDecodeError) as exc:
        raise SkillDiffError(f"Invalid snapshot JSON: {path}") from exc
    validate(obj)
    return obj


def validate(obj: dict) -> None:
    if not isinstance(obj, dict) or obj.get("schema") != SCHEMA:
        raise SkillDiffError("Unsupported snapshot schema")
    files = obj.get("files")
    if not isinstance(files, dict) or "SKILL.md" not in files or len(files) > MAX_FILES:
        raise SkillDiffError("Invalid snapshot file inventory")
    total = 0
    for name, record in files.items():
        if (not isinstance(name, str) or not name or "\\" in name or ":" in name
                or name.startswith("/") or any(x in {"", ".", ".."} for x in name.split("/"))):
            raise SkillDiffError("Invalid snapshot path")
        if not isinstance(record, dict) or not {"sha256", "size", "text"} <= record.keys():
            raise SkillDiffError(f"Invalid file record: {name}")
        size, checksum, text = record["size"], record["sha256"], record["text"]
        if type(size) is not int or not 0 <= size <= MAX_FILE:
            raise SkillDiffError(f"Invalid file size: {name}")
        total += size
        if total > MAX_TOTAL or not isinstance(checksum, str) or not re.fullmatch(r"[0-9a-f]{64}", checksum):
            raise SkillDiffError(f"Invalid snapshot hash or total size: {name}")
        if text is not None:
            if not isinstance(text, str):
                raise SkillDiffError(f"Invalid text: {name}")
            try:
                encoded = text.encode("utf-8")
            except UnicodeEncodeError as exc:
                raise SkillDiffError(f"Invalid UTF-8 text: {name}") from exc
            if len(encoded) != size or sha(encoded) != checksum:
                raise SkillDiffError(f"Snapshot content/hash mismatch: {name}")
    if files["SKILL.md"]["text"] is None or obj.get("digest") != digest(files):
        raise SkillDiffError("Invalid snapshot digest or SKILL.md encoding")


URL = re.compile(r"https?://[^\s<>\x00-\x1f\x7f\x22'`]+", re.I)
SENSITIVE = re.compile(r"(?<![\w.-])(?:~[/\\])?(?:\.env(?:\.[\w-]+)?|\.ssh(?:[/\\][\w.-]+)?|\.aws[/\\]credentials|\.kube[/\\]config)(?![\w.-])", re.I)
EXECUTION = re.compile(r"\b(?:curl|wget)\b[^\r\n]*\|\s*(?:ba)?sh\b|\b(?:eval|exec)\s*\(|\bsubprocess\.(?:run|Popen|call|check_output|check_call)\s*\(|\bos\.system\s*\(|\bInvoke-Expression\b", re.I)
MARKDOWN_LINK = re.compile(r"\[[^\]\n]*\]\(<?([^\s)>]+)>?(?:\s+[^)]*)?\)")
BACKTICK = re.compile(r"(?<!`)`([^`\n]+)`(?!`)")
AT_REF = re.compile(r"(?<![\w@])@((?:\.?\.?/)?[\w./-]+\.[\w-]+)")


def evidence(snapshot: dict) -> list[dict]:
    found = []
    for path, record in sorted(snapshot["files"].items()):
        if record["text"] is None:
            continue
        lines = record["text"].splitlines()
        for i, line in enumerate(lines, 1):
            def add(kind: str, value: str, priority: str) -> None:
                found.append({"kind": kind, "value": value, "priority": priority,
                              "path": path, "line": i, "excerpt": line.strip()[:500]})
            for match in URL.finditer(line):
                try:
                    url = urlsplit(match.group().rstrip(".,;)]}"))
                    host = url.hostname
                    if host:
                        port = url.port
                        add("network-host", host.lower() + (f":{port}" if port else ""), "medium")
                except ValueError:
                    pass  # The whole file change remains visible.
            for match in SENSITIVE.finditer(line):
                add("sensitive-path", match.group().replace("\\", "/"), "high")
            for match in EXECUTION.finditer(line):
                add("execution-pattern", match.group().strip(), "high")
        # Preserve the declaration as text instead of pretending to implement YAML.
        if path == "SKILL.md" and lines and lines[0].lstrip("\ufeff").strip() == "---":
            for i in range(1, len(lines)):
                if lines[i].strip() in {"---", "..."}:
                    break
                if re.match(r"^allowed-tools\s*:", lines[i]):
                    block = [lines[i].split(":", 1)[1].strip()]
                    j = i + 1
                    while j < len(lines) and (lines[j].startswith((" ", "\t", "- ")) or not lines[j].strip()):
                        block.append(lines[j].strip())
                        j += 1
                    value = " ".join(block).strip()
                    if value:
                        found.append({"kind": "tool-declaration", "value": value, "priority": "medium",
                                      "path": path, "line": i + 1, "excerpt": lines[i][:500]})
    return found


def references(snapshot: dict) -> dict:
    files = snapshot["files"]
    edges, unresolved = [], []
    for source, record in sorted(files.items()):
        text = record["text"]
        if text is None or not source.lower().endswith((".md", ".mdx", ".txt")):
            continue
        seen = set()
        for line_number, line in enumerate(text.splitlines(), 1):
            candidates = [(m.group(1), True) for m in MARKDOWN_LINK.finditer(line)]
            candidates += [(m.group(1), False) for m in BACKTICK.finditer(line)]
            candidates += [(m.group(1), False) for m in AT_REF.finditer(line)]
            for raw, explicit in candidates:
                if raw.startswith(("#", "//")) or re.match(r"^[a-zA-Z][\w+.-]*:", raw):
                    continue
                candidate = unquote(raw.split("#", 1)[0].split("?", 1)[0]).replace("\\", "/")
                if not candidate or (not explicit and any(c.isspace() for c in candidate)):
                    continue
                parts = list(PurePosixPath(source).parent.parts)
                escaped = candidate.startswith("/")
                for part in candidate.split("/"):
                    if part == "..":
                        if parts:
                            parts.pop()
                        else:
                            escaped = True
                    elif part not in {"", "."}:
                        parts.append(part)
                target = "/".join(parts)
                # Inline code is only treated as a reference if it looks like a path.
                if not explicit and target not in files and not re.search(r"(?:^|/)[\w.-]+\.(?:md|mdx|txt|py|sh|js|ts|json|yaml|yml|ps1)$", candidate):
                    continue
                key = (target, escaped)
                if key in seen:
                    continue
                seen.add(key)
                item = {"source": source, "target": candidate if escaped else target, "line": line_number}
                if escaped:
                    unresolved.append({**item, "reason": "outside-skill"})
                elif target in files:
                    edges.append(item)
                else:
                    unresolved.append({**item, "reason": "missing"})
    routes = {"SKILL.md": ["SKILL.md"]}
    adjacency: dict[str, list[str]] = {}
    for edge in edges:
        adjacency.setdefault(edge["source"], []).append(edge["target"])
    queue = deque(["SKILL.md"])
    while queue:
        source = queue.popleft()
        for target in sorted(adjacency.get(source, [])):
            if target not in routes:
                routes[target] = routes[source] + [target]
                queue.append(target)
    return {"edges": edges, "unresolved": unresolved, "routes": routes}


def compare(before: dict, after: dict) -> dict:
    old, new = before["files"], after["files"]
    old_graph, new_graph = references(before), references(after)
    changes = []
    for path in sorted(old.keys() | new.keys()):
        a, b = old.get(path), new.get(path)
        if a is not None and b is not None and a["sha256"] == b["sha256"]:
            continue
        status = "added" if a is None else "removed" if b is None else "modified"
        changes.append({"path": path, "status": status,
                        "before": a, "after": b,
                        "route_before": old_graph["routes"].get(path),
                        "route_after": new_graph["routes"].get(path)})
    # Compare per-file evidence sets. Moving a capability into a new file is reviewable.
    def index(snap: dict) -> dict:
        result = {}
        for item in evidence(snap):
            result.setdefault((item["path"], item["kind"], item["value"]), item)
        return result
    a, b = index(before), index(after)
    signals = [{**b[k], "change": "added"} for k in sorted(b.keys() - a.keys())]
    signals += [{**a[k], "change": "removed"} for k in sorted(a.keys() - b.keys())]
    priority_order = {"high": 0, "medium": 1}
    signals.sort(key=lambda s: (s["change"] != "added", priority_order[s["priority"]], s["path"], s["line"], s["kind"], s["value"]))
    return {"schema": "skill-diff/report-v1", "before_digest": before["digest"], "after_digest": after["digest"],
            "changed": bool(changes), "files": changes, "signals": signals,
            "references_before": old_graph, "references_after": new_graph,
            "summary": {"files_before": len(old), "files_after": len(new), "changed_files": len(changes),
                        "added_signals": sum(s["change"] == "added" for s in signals),
                        "removed_signals": sum(s["change"] == "removed" for s in signals),
                        "bytes_before": sum(f["size"] for f in old.values()),
                        "bytes_after": sum(f["size"] for f in new.values())}}
