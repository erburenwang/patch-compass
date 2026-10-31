from __future__ import annotations

import json
import string


def _quoted(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _markdown_cell(value: str) -> str:
    rendered = _quoted(value)
    return "".join("\\" + character if character in string.punctuation else character for character in rendered)


def _text_report(report: dict) -> str:
    base = report["base"]
    lines = [
        "Patch Compass review",
        f"Base: {base['ref']} (merge-base {base['mergeBase']})",
        f"Changed paths: {report['changedCount']}",
        "",
        "Categories:",
    ]
    nonzero = [(name, count) for name, count in report["categoryCounts"].items() if count]
    lines.extend([f"  {name}: {count}" for name, count in nonzero] or ["  (none)"])
    lines.extend(["", "Changed paths:"])
    if report["changes"]:
        lines.extend(
            f"  {item['status']} {_quoted(item['path'])} — {', '.join(item['categories']) or 'other'}"
            for item in report["changes"]
        )
    else:
        lines.append("  No changed paths were found.")

    lines.extend(["", "Review checklist:"])
    if report["prompts"]:
        for prompt in report["prompts"]:
            lines.append(f"  [ ] {prompt['title']}: {prompt['message']}")
            lines.append("      Evidence: " + ", ".join(_quoted(path) for path in prompt["evidencePaths"]))
    else:
        lines.append("  No review prompts were triggered by these paths.")
    lines.extend(["", "Path-based reminders only. The report contains paths and statuses, not diff or file contents."])
    return "\n".join(lines)


def _markdown_report(report: dict) -> str:
    base = report["base"]
    lines = [
        "# Patch Compass review",
        "",
        f"- Base: {_markdown_cell(base['ref'])}",
        f"- Merge base: `{base['mergeBase']}`",
        f"- Changed paths: **{report['changedCount']}**",
        "",
        "## Changed paths",
        "",
        "| Status | Path | Categories |",
        "| --- | --- | --- |",
    ]
    if report["changes"]:
        for item in report["changes"]:
            categories = ", ".join(item["categories"]) or "other"
            lines.append(f"| {item['status']} | {_markdown_cell(item['path'])} | {categories} |")
    else:
        lines.append("| — | No changed paths were found | — |")

    lines.extend(["", "## Review checklist", ""])
    if report["prompts"]:
        for prompt in report["prompts"]:
            evidence = ", ".join(_markdown_cell(path) for path in prompt["evidencePaths"])
            lines.append(f"- [ ] **{prompt['title']}** — {prompt['message']}")
            lines.append(f"  - Evidence: {evidence}")
    else:
        lines.append("No review prompts were triggered by these paths.")
    lines.extend(
        [
            "",
            "These are path-based review reminders, not a correctness verdict. The report contains no diff or file contents.",
        ]
    )
    return "\n".join(lines)


def render_report(report: dict, output_format: str) -> str:
    if output_format == "json":
        return json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True)
    if output_format == "markdown":
        return _markdown_report(report)
    if output_format == "text":
        return _text_report(report)
    raise ValueError(f"Unsupported report format: {output_format}")
