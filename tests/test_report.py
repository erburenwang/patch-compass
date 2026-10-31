from __future__ import annotations

import json
import unittest

from patch_compass.analysis import analyze
from patch_compass.git_ops import ChangeSet, ChangedPath
from patch_compass.report import render_report


class ReportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.report = analyze(
            ChangeSet("main", "abc123", [ChangedPath("src/a`b\n树.py", "M")])
        )

    def test_json_report_round_trips_unusual_paths(self) -> None:
        rendered = render_report(self.report, "json")

        decoded = json.loads(rendered)
        self.assertEqual("src/a`b\n树.py", decoded["changes"][0]["path"])
        self.assertEqual(1, decoded["schemaVersion"])

    def test_markdown_report_contains_review_checklist(self) -> None:
        rendered = render_report(self.report, "markdown")

        self.assertIn("# Patch Compass review", rendered)
        self.assertIn("## Review checklist", rendered)
        self.assertIn(r"src\/a", rendered)

    def test_markdown_base_ref_with_backtick_stays_plain_text(self) -> None:
        report = analyze(ChangeSet("feature/a`b", "abc123", []))

        rendered = render_report(report, "markdown")

        self.assertIn(r"feature\/a\`b", rendered)

    def test_markdown_escapes_untrusted_path_markup(self) -> None:
        path = "src/[click](https://evil.example)|<img src=x>.py"
        report = analyze(ChangeSet("main", "abc123", [ChangedPath(path, "M")]))

        rendered = render_report(report, "markdown")

        self.assertNotIn("[click](https://evil.example)", rendered)
        self.assertNotIn("<img src=x>", rendered)
        self.assertIn(r"\[click\]", rendered)
        self.assertIn(r"\|", rendered)
        self.assertIn(r"\<img", rendered)

    def test_text_report_states_read_only_review_scope(self) -> None:
        rendered = render_report(self.report, "text")

        self.assertIn("Base: main", rendered)
        self.assertIn("report contains paths and statuses", rendered)
        self.assertIn("not diff or file contents", rendered)

    def test_unknown_format_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            render_report(self.report, "html")


if __name__ == "__main__":
    unittest.main()
