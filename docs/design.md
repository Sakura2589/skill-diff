# Design and comparison contract

SkillDiff is a deterministic review aid for **one skill directory at a time**. It has no runtime dependencies and does not interpret skill instructions as authority.

## Data flow

```text
local directory ── bounded read ── snapshot ──┐
                                            ├── compare ── report
directory or validated snapshot ────────────┘
                                               ├── file changes
                                               ├── added/removed literal signals
                                               └── before/after reference routes
```

1. A directory must contain a UTF-8 `SKILL.md`. All regular files are read and hashed. There is no YAML validity requirement: even malformed instructions need review.
2. Every file stores a SHA-256 hash, byte size, and UTF-8 text or `null` for binary/non-UTF-8. Original line endings are retained. A digest covers sorted `[path, hash, size]` tuples serialized as compact ASCII JSON.
3. A saved snapshot is schema-validated. Text contents must match their recorded byte sizes and hashes; its inventory digest is verified. Binary hashes cannot be independently verified without the original binary bytes. Snapshots are not signed and are trusted baseline inputs, not attestations.
4. A comparison uses relative paths as file identity and byte hashes as content identity. Renames are removals plus additions. Line endings count as changes. Permissions, timestamps, ownership, and empty directories are not compared.
5. Signals are deduplicated by `(path, kind, value)`, retaining the first evidence line. A moved line does not generate a new signal; moving it to another file does. Changing a URL's path without changing its host appears in the file diff, not as a new host signal.
6. Graph traversal starts at `SKILL.md`, uses breadth-first search, and handles cycles. One deterministic shortest route is displayed; JSON includes all detected edges. References are relative to the file containing the reference. Removed files retain their old route. Unreferenced files are still tracked.

## Signal definitions in v0.1

| Kind | Literal inputs | Priority |
|---|---|---|
| `network-host` | HTTP(S) URLs; lowercase hostname and explicit port | medium |
| `sensitive-path` | `.env` variants, `.ssh` paths, `.aws/credentials`, `.kube/config` | high |
| `execution-pattern` | curl/wget piped to sh/bash; eval/exec calls; common subprocess calls; os.system; Invoke-Expression | high |
| `tool-declaration` | A top-level `allowed-tools:` field in SKILL.md frontmatter; indented continuation lines retained | medium |

These patterns are intentionally explainable and incomplete. Examples, negations, and comments are not treated as proof of execution. There is no safety score, no model judge, and no vulnerability verdict.

## Snapshot format

```json
{
  "schema": "skill-diff/snapshot-v1",
  "digest": "<sha256 of canonical inventory>",
  "files": {
    "SKILL.md": {
      "sha256": "<sha256 of original bytes>",
      "size": 12,
      "text": "# My skill\n\n"
    }
  }
}
```

The example uses placeholder hashes. Snapshot files contain source text, not just metadata. They must live outside the scanned directory. Timestamps, usernames, and absolute paths are not included; identical bytes and paths give identical snapshots across machines.

## Report format

`skill-diff/report-v1` includes before/after digests; summary counters; file records with before/after contents and routes; added/removed signals with path/line/excerpt; and before/after reference graphs. JSON is the complete machine-readable record. There is no promise of report-schema stability until 1.0; version fields make incompatible changes explicit.

## Resource and trust boundaries

- 5,000 regular files, 8 MiB each, 64 MiB total; snapshot input limited to 128 MiB.
- Only `.git` and `__pycache__` directories are excluded. Hidden files are included.
- Nested symlinks and Windows reparse points cause failure; resolving the explicitly supplied root is allowed. No external target is followed by reference parsing.
- The scanner assumes a stable directory during the scan. It is **not a sandbox against a concurrent process modifying files or swapping links**. Compare immutable checkouts for hostile inputs.
- Files are read as data. No subprocess, imports, network fetches, plugin hooks, or post-install scripts come from reviewed content.
- HTML output escapes content and applies a restrictive CSP; it uses no JavaScript or external fonts/assets. Terminal output neutralizes escape/control and bidi override characters. JSON retains source content with JSON escaping.
- Full JSON/snapshot contents may contain secrets. Other renderers can contain excerpts and diffs with secrets too. No output is automatically redacted or uploaded.
- HTML text previews stop at 200,000 combined characters or 2,000 diff lines. Omission/truncation is visible. Binary content displays hashes. All these changes still count toward the gate.
- A matching digest proves only byte identity within scope. It does not verify origin, author, previous approval, executable mode, or external dependencies.

## Why no automatic approval file?

v0.1 keeps the approval boundary in the team's existing code review. A reviewer may replace a baseline after inspecting the report. Checking against a baseline from the trusted base branch avoids silently accepting a candidate's self-updated baseline. See [CI](ci.md).
