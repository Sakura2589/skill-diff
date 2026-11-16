# Security scope

SkillDiff is a static review aid, not a sandbox, malware detector, or approval authority. Read [the design boundary](docs/design.md) before using it as a gate.

Untrusted file content must never be executed or rendered as active markup. Failures to enforce this boundary, path escapes, and silent incomplete scans are security-relevant bugs. Submit a minimal sanitized reproducer through GitHub's private vulnerability reporting if available. If private reporting is not enabled, open a minimal issue asking for a private contact without exploit details or sensitive files.

Never upload real secrets, private skill contents, or unredacted snapshots. No guarantee of a response time or a paid bounty is made.
