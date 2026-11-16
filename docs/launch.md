# Launch kit

Everything below is draft copy. No social posts, messages, outreach, or package publication have been performed by this repository.

## Repository metadata

Name: `skill-diff`

Description: `See what changed behind SKILL.md. Offline skill update reviews with reference chains, snapshots, and visual diffs. Zero runtime dependencies.`

Suggested topics: `agent-skills`, `ai-agents`, `developer-tools`, `code-review`, `cli`, `python`, `diff`, `claude-code`, `codex`.

## English announcement draft

I built SkillDiff to answer a small question: my AI skill updated, but what actually changed?

In the demo, SKILL.md is identical in both versions. A referenced workflow and a script change underneath it. SkillDiff follows that chain and shows the exact diff, new host mentions, and sensitive-path references in one offline HTML report.

It's a Python CLI with zero runtime dependencies, no model calls, and no telemetry. It never runs the skill. The matches are review signals, not a safety verdict; all file changes remain visible even when no rule matches.

I'd like feedback from people who maintain or review skill collections, especially small sanitized examples of updates where reference tracing would help.

## 中文发布草稿

我做了一个小工具 SkillDiff，专门回答：AI Skill 更新以后，究竟改变了什么？

演示里的 SKILL.md 完全没改，变化发生在它引用的参考文档和脚本中。工具会沿引用链定位变化，展示新增域名、敏感路径和原始 diff，输出一份本地 HTML 报告。

零运行时依赖，不需要 API Key，也不执行 Skill。它不是安全认证，规则匹配只是帮助定位审查重点；没有命中规则的文本变化也会保留。

欢迎维护 Skill 的朋友用自己的更新试试，尤其想收集脱敏后的真实引用链案例。

## A short demo recording

1. Show the identical before/after `SKILL.md` files.
2. Run `python -m skill_diff diff examples/before examples/after`.
3. Open the HTML report and follow the route into `scripts/summarize.py`.
4. Show the exact change and explain that mentions do not prove execution.
5. Run `check` against a baseline to demonstrate a nonzero exit code.

## Release checklist

- Run tests and install a built wheel outside the source tree.
- Inspect desktop and narrow report layouts; check readable evidence and diffs.
- Confirm public docs contain no private paths, credentials, or fabricated claims.
- Push source; wait for the actual CI matrix before claiming cross-platform validation.
- Tag the reviewed commit, attach built distributions, and publish accurate release notes.
- Confirm package-name ownership before any PyPI release.
- Ask for specific feedback in communities that allow project sharing. Do not mass-post or open promotional issues on unrelated projects.

Track successful first runs, repeat use, and useful reports before treating stars as a product metric.
