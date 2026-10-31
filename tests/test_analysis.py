from __future__ import annotations

import unittest

from patch_compass.analysis import analyze, classify_path
from patch_compass.git_ops import ChangeSet, ChangedPath


class AnalysisTests(unittest.TestCase):
    def test_classifies_common_review_areas(self) -> None:
        cases = {
            "src/app.py": ("code",),
            "tests/test_app.py": ("tests",),
            "pyproject.toml": ("dependencies",),
            "uv.lock": ("lockfiles",),
            "db/migrations/0002_add_index.sql": ("migrations",),
            "openapi/service.yaml": ("api",),
            ".github/workflows/ci.yml": ("ci",),
            "docs/setup.md": ("docs",),
            "dist/app.min.js": ("generated",),
        }

        for path, expected in cases.items():
            with self.subTest(path=path):
                self.assertEqual(expected, classify_path(path))

    def test_source_without_test_path_gets_evidence_linked_prompt(self) -> None:
        report = analyze(ChangeSet("main", "abc123", [ChangedPath("src/app.py", "M")]))

        prompt = next(item for item in report["prompts"] if item["id"] == "test-coverage")
        self.assertEqual(["src/app.py"], prompt["evidencePaths"])
        self.assertIn("regression", prompt["message"].lower())

    def test_changed_test_path_suppresses_missing_test_prompt(self) -> None:
        changes = ChangeSet(
            "main",
            "abc123",
            [ChangedPath("src/app.py", "M"), ChangedPath("tests/test_app.py", "A")],
        )

        report = analyze(changes)

        self.assertNotIn("test-coverage", {item["id"] for item in report["prompts"]})

    def test_dependency_manifest_without_lock_change_gets_prompt(self) -> None:
        report = analyze(ChangeSet("main", "abc123", [ChangedPath("package.json", "M")]))

        prompt = next(item for item in report["prompts"] if item["id"] == "lockfile-review")
        self.assertEqual(["package.json"], prompt["evidencePaths"])

    def test_special_path_categories_get_their_review_prompts(self) -> None:
        paths = [
            "db/migrations/0003_add_index.sql",
            ".github/workflows/release.yml",
            "dist/client.min.js",
            "docs/deploy.md",
        ]
        report = analyze(ChangeSet("main", "abc123", [ChangedPath(path, "M") for path in paths]))

        prompts = {item["id"]: item["evidencePaths"] for item in report["prompts"]}
        self.assertEqual(
            {
                "migration-coverage": ["db/migrations/0003_add_index.sql"],
                "workflow-security": [".github/workflows/release.yml"],
                "generated-source": ["dist/client.min.js"],
                "documentation-alignment": ["docs/deploy.md"],
            },
            prompts,
        )

        api_report = analyze(ChangeSet("main", "abc123", [ChangedPath("openapi/service.yaml", "M")]))
        api_prompt = next(item for item in api_report["prompts"] if item["id"] == "api-compatibility")
        self.assertEqual(["openapi/service.yaml"], api_prompt["evidencePaths"])

    def test_no_changes_produces_empty_categories_and_prompts(self) -> None:
        report = analyze(ChangeSet("main", "abc123", []))

        self.assertEqual(0, report["changedCount"])
        self.assertEqual([], report["prompts"])
        self.assertEqual([], report["changes"])


if __name__ == "__main__":
    unittest.main()
