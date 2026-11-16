# Validation record

Date: 2026-11-16. Version: 0.1.0 alpha.

## Completed locally

- Windows / Python 3.13.5: **50 passed, 1 skipped** with `python -m pytest -q`.
- The skipped test requires symlink-creation privilege that was unavailable. Other path-boundary tests passed. The Linux/macOS CI jobs are configured to exercise the symlink case.
- Built a `py3-none-any` wheel with setuptools, without runtime dependencies.
- Installed that wheel into a clean virtual environment using `--no-index --no-deps`.
- Ran the installed command from outside the source directory: version output and HTML report generation succeeded, including access to the packaged CSS asset.
- Parsed the CI workflow YAML and compiled the Python sources.
- The demo produces 3 changed files and 4 added signals while `SKILL.md` remains identical.
- Regression tests cover prose-only drift, binary changes, added/removed files, reference cycles, missing/outside references, encoded paths, snapshot corruption, duplicate JSON keys, line moves, resource limits, exit policies, output guards, HTML/Markdown injection, terminal controls, and explicit diff-preview limits.

## Not yet verified

- Browser visual QA: the authoring environment's browser policy blocked the local preview. The responsive CSS and HTML output were authored and structurally tested, but desktop/mobile browser appearance and assistive-technology behavior have not been visually accepted.
- Remote CI: configured for Windows, Linux, and macOS with Python 3.10 and 3.13; consult the actual GitHub Actions runs for current results. A workflow file alone is not evidence that these jobs passed.
- Public package publication, real-world adoption, large-corpus accuracy, adversarial concurrency, and runtime agent behavior are not validated.

The project deliberately avoids claiming a detection rate, a security certification, or guaranteed compatibility with a specific agent runtime.
