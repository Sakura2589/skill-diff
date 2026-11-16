# Contributing

Start with a sanitized before/after example and explain what you expected the report to show. Small fixes with reproducible cases are welcome.

```sh
python -m pip install pytest
python -m pytest -q
python -m skill_diff diff examples/before examples/after --format html -o review.html
```

Keep runtime dependencies at zero unless there is a compelling, discussed need. Separate parsing/comparison from presentation. Every finding needs a source path and line. Call text matches “signals,” not confirmed execution or vulnerabilities. Changes that affect parsing, hashes, references, or exit codes need a regression test that exercises observable behavior.

For report changes, inspect desktop and narrow layouts and ensure input text cannot introduce HTML or terminal control sequences. Do not load third-party fonts, analytics, or scripts.

Do not attach credentials, private snapshots, or proprietary skills to issues. Use small fictional fixtures or public content with a compatible license. Contributions are accepted under the MIT license.
