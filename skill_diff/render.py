"""Render reports without interpreting skill content as markup or commands."""
from __future__ import annotations

import difflib
import html
import json
import re
from importlib.resources import files

NOTICE = "Signals are literal text matches, not proof of execution or a safety verdict. Review all changed files."
MAX_DIFF_CHARS = 200_000
MAX_DIFF_LINES = 2000


def safe_text(value: str) -> str:
    # Neutralize terminal escapes, bidi overrides and other invisible controls.
    return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f\u202a-\u202e\u2066-\u2069]",
                  lambda m: f"\\u{ord(m.group()):04x}", str(value))


def esc(value: str) -> str:
    return html.escape(safe_text(value), quote=True)


def md(value: str) -> str:
    text = html.escape(safe_text(value), quote=True).replace("\n", " ").replace("\r", " ")
    for character in "\\`*_{}[]()#+!|":
        text = text.replace(character, f"&#{ord(character)};")
    return text


def text_report(report: dict) -> str:
    s = report["summary"]
    lines = ["SkillDiff / update review", "=" * 50,
             f"{s['changed_files']} changed files | +{s['added_signals']} / -{s['removed_signals']} signals",
             f"Before {report['before_digest'][:12]} -> after {report['after_digest'][:12]}", ""]
    if not report["changed"]:
        lines.append("No file content changes in the scanned scope.")
    for signal in report["signals"]:
        marker = "+" if signal["change"] == "added" else "-"
        lines.append(f"{marker} [{signal['priority'].upper()}] {signal['kind']}: {signal['value']}")
        lines.append(f"    {signal['path']}:{signal['line']} | {signal['excerpt']}")
    lines += ["", "Changed files"]
    for change in report["files"]:
        lines.append(f"  {change['status']:8} {change['path']}")
        route = change["route_after"] or change["route_before"]
        lines.append("           " + (" -> ".join(route) if route else "No static route from SKILL.md; file is still tracked."))
    issues = report["references_after"]["unresolved"]
    if issues:
        lines += ["", f"Unresolved references after update: {len(issues)}"]
        lines += [f"  {x['source']}:{x['line']} -> {x['target']} ({x['reason']})" for x in issues]
    lines += ["", NOTICE]
    return safe_text("\n".join(lines)) + "\n"


def markdown_report(report: dict) -> str:
    s = report["summary"]
    lines = ["## SkillDiff update review", "",
             f"**{s['changed_files']} changed files · +{s['added_signals']} / −{s['removed_signals']} signals**", "",
             f"Before: `{report['before_digest'][:12]}` → after: `{report['after_digest'][:12]}`", "",
             "| Change | Priority | Signal | Evidence |", "|---|---|---|---|"]
    for x in report["signals"]:
        lines.append(f"| {x['change']} | {x['priority']} | {md(x['kind'])}: {md(x['value'])} | {md(x['path'])}:{x['line']} |")
    lines += ["", "### Changed files", "", "| Status | File | Reference route |", "|---|---|---|"]
    for x in report["files"]:
        route = x["route_after"] or x["route_before"]
        lines.append(f"| {x['status']} | {md(x['path'])} | {md(' → '.join(route)) if route else 'No static route; still tracked'} |")
    issues = report["references_after"]["unresolved"]
    if issues:
        lines += ["", "### Unresolved references after update", ""]
        lines += [f"- {md(x['source'])}:{x['line']} → {md(x['target'])} ({x['reason']})" for x in issues]
    lines += ["", f"> {NOTICE}", ""]
    return "\n".join(lines)


def diff_lines(change: dict) -> tuple[list[str], str | None]:
    a, b = change["before"], change["after"]
    if any(x is not None and x["text"] is None for x in (a, b)):
        return [], "Binary or non-UTF-8 content: compare the hashes below; text analysis was unavailable."
    old = a["text"] if a else ""
    new = b["text"] if b else ""
    if len(old) + len(new) > MAX_DIFF_CHARS:
        return [], "Text preview omitted above 200,000 characters. Full contents remain in JSON and snapshots."
    iterator = difflib.unified_diff(old.splitlines(), new.splitlines(), fromfile="before/" + change["path"], tofile="after/" + change["path"], lineterm="")
    result = []
    for line in iterator:
        if len(result) == MAX_DIFF_LINES:
            return result, "Preview truncated at 2,000 lines. Full contents remain in JSON and snapshots."
        result.append(line)
    if not result and old != new:
        return [], "Only line endings or the final newline changed. Byte hashes below differ."
    return result, None


def html_report(report: dict) -> str:
    s = report["summary"]
    css = files("skill_diff").joinpath("report.css").read_text(encoding="utf-8")
    signals = []
    for x in report["signals"]:
        marker = "+" if x["change"] == "added" else "−"
        signals.append(f'''<article class="signal {x['change']}">
          <div class="signal-top"><span class="pill {x['priority']}">{x['priority']} review priority</span><span class="mono change">{marker} {x['change']}</span></div>
          <h3>{esc(x['kind'])}</h3><p class="signal-value mono">{esc(x['value'])}</p>
          <p class="location mono">{esc(x['path'])}:{x['line']}</p>
          <pre class="evidence">{esc(x['excerpt'])}</pre></article>''')
    changes = []
    for i, x in enumerate(report["files"]):
        rows, note = diff_lines(x)
        preview = []
        for row in rows:
            kind = "meta" if row.startswith(("---", "+++", "@@")) else "plus" if row.startswith("+") else "minus" if row.startswith("-") else "context"
            preview.append(f'<div class="diff-line {kind}">{esc(row) or " "}</div>')
        routes = []
        for side in ("before", "after"):
            route = x[f"route_{side}"]
            if route:
                routes.append(f'<p class="route"><b>{side}</b> ' + ' <span>→</span> '.join(f'<code>{esc(part)}</code>' for part in route) + '</p>')
        if not routes:
            routes = ['<p class="route">No static route from SKILL.md. This bundled file is still tracked.</p>']
        hashes = []
        for side in ("before", "after"):
            f = x[side]
            hashes.append(f'<div><b>{side}</b> <code>{f["sha256"] if f else "absent"}</code> <span>{str(f["size"]) + " bytes" if f else ""}</span></div>')
        changes.append(f'''<details class="file" open><summary><span class="file-name mono">{esc(x['path'])}</span><span class="pill neutral">{x['status']}</span></summary>
        <div class="file-body">{''.join(routes)}<div class="diff">{''.join(preview)}</div>
        {f'<p class="preview-note">{esc(note)}</p>' if note else ''}<div class="hashes">{''.join(hashes)}</div></div></details>''')
    issues = report["references_after"]["unresolved"]
    unresolved = ""
    if issues:
        items = "".join(f'<li><code>{esc(x["source"])}:{x["line"]}</code> → <code>{esc(x["target"])}</code><span class="pill neutral">{x["reason"]}</span></li>' for x in issues)
        unresolved = f'<section id="references"><div class="section-title"><h2>Unresolved references</h2><span>{len(issues)} after update</span></div><p>These targets were not followed. Outside files are outside the review boundary.</p><ul class="unresolved">{items}</ul></section>'
    status = "Changes to review" if report["changed"] else "No content changes"
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<title>SkillDiff · Update review</title><style>{css}</style></head>
<body><header><a class="brand" href="#top"><span class="brand-mark">Δ</span> SkillDiff<span class="version">/ 0.1</span></a><nav><a href="#signals">Signals</a><a href="#files">Files</a><a href="#scope">Review scope</a></nav><span class="local">● LOCAL REPORT</span></header>
<main id="top"><section class="hero"><p class="eyebrow">AGENT SKILLS / UPDATE REVIEW</p><div class="hero-grid"><div><h1>Small update.<br>See the <em>whole change.</em></h1><p class="intro">Follow the files behind your skill. Review new signals,<br class="wide"> trace references, and inspect the exact diff.</p></div><div class="status-card"><span class="status-dot"></span><span>{status}</span><p class="mono">{report['before_digest'][:12]}<br><span>↓</span><br>{report['after_digest'][:12]}</p><small>Content fingerprints · SHA-256</small></div></div></section>
<div class="metrics"><div><strong>{s['changed_files']:02}</strong><span>changed files</span></div><div><strong class="accent">+{s['added_signals']:02}</strong><span>added signals</span></div><div><strong>−{s['removed_signals']:02}</strong><span>removed signals</span></div><div><strong>{s['files_after']:02}</strong><span>files tracked after</span></div></div>
<div class="notice"><b>Evidence, with context.</b> {NOTICE}</div>
<section id="signals"><div class="section-title"><h2>01 <span>Signal changes</span></h2><span>New evidence first</span></div><div class="signals">{''.join(signals) or '<p class="empty">No signal changes matched. File changes still need review.</p>'}</div></section>
<section id="files"><div class="section-title"><h2>02 <span>Follow the change</span></h2><span>Click a file to collapse</span></div>{''.join(changes) or '<p class="empty">All tracked file contents match.</p>'}</section>
{unresolved}<section id="scope" class="scope"><p class="eyebrow">READ THE BOUNDARY</p><h2>A review aid. Your judgment stays in the loop.</h2><div class="scope-grid"><p>Every regular file is byte-hashed, including unreferenced assets. UTF-8 files are checked for literal hosts, sensitive paths, execution patterns, and the SKILL.md tool declaration.</p><p>References are static Markdown links, path-like inline code, and @file references. Dynamic imports, runtime behavior, external content, and natural-language intent are not resolved. Links and scripts are never executed.</p><p>Excluded directories: .git and __pycache__. Symlinks, unreadable files, and exceeded scan limits stop the scan. Snapshots and reports may contain source text and secrets: share them deliberately.</p></div></section>
</main><footer><span class="brand">Δ SkillDiff</span><span>No API key. No telemetry. No remote assets.</span><span class="mono">REPORT FORMAT v1</span></footer></body></html>'''


def render(report: dict, format_name: str) -> str:
    if format_name == "json":
        return json.dumps(report, ensure_ascii=True, indent=2) + "\n"
    return {"text": text_report, "markdown": markdown_report, "html": html_report}[format_name](report)
