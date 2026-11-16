# CI: compare against a trusted baseline

First review a skill locally and record it:

```sh
skill-diff snapshot .agents/skills/my-skill -o baselines/my-skill.json
```

Create `baselines/` first. Commit the baseline only after reviewing its contents; snapshots include source text. Review and protect baseline updates using your existing CODEOWNERS and branch rules.

The following recipe runs on pull requests in a **consumer repository**. It checks the candidate skill against the baseline from the base commit, not the candidate's possibly edited baseline. Install a reviewed, immutable SkillDiff commit. Replace `REVIEWED_SKILLDIFF_COMMIT_SHA` and `my-skill` before use.

```yaml
name: Skill update review
on: pull_request
permissions:
  contents: read
jobs:
  review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@11d5960a326750d5838078e36cf38b85af677262 # v4
        with:
          persist-credentials: false
      - uses: actions/checkout@11d5960a326750d5838078e36cf38b85af677262 # v4
        with:
          ref: ${{ github.event.pull_request.base.sha }}
          path: trusted-base
          persist-credentials: false
      - uses: actions/checkout@11d5960a326750d5838078e36cf38b85af677262 # v4
        with:
          repository: Sakura2589/skill-diff
          ref: REVIEWED_SKILLDIFF_COMMIT_SHA
          path: skill-diff-tool
          persist-credentials: false
      - uses: actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065 # v5
        with:
          python-version: '3.13'
      - name: Check candidate using trusted tool code
        working-directory: skill-diff-tool
        run: >-
          python -m skill_diff check
          ../trusted-base/baselines/my-skill.json
          ../.agents/skills/my-skill
          --format markdown -o ../skill-review.md
      - name: Add review summary, including on a failed gate
        if: always()
        shell: bash
        run: |
          if [ -f skill-review.md ]; then
            cat skill-review.md >> "$GITHUB_STEP_SUMMARY"
          fi
```

This is an intentionally strict gate: every candidate content change fails until the team deliberately accepts and updates the trusted baseline through its approval process. Updating the baseline inside the same unmerged PR does **not** self-approve the change. To introduce an intended update, use the team's reviewed exception/merge process and update the baseline for subsequent PRs. SkillDiff does not implement reviewer authentication.

Missing or malformed baselines fail with exit 2. Do not turn this into an empty baseline fallback. `--fail-on signals` and `--fail-on high` are available for less strict workflows but can miss significant prose changes.

Run on `pull_request`, not `pull_request_target` with candidate code. Keep the tool checkout trusted and separate. Reports contain source text; check whether CI summaries and artifacts are appropriate for your repository's audience. This recipe does not post comments or upload files automatically.

Action refs above were resolved to commit SHAs during initial authoring. Review dependency updates before changing them.
