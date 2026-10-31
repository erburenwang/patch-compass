from __future__ import annotations

import io
import json
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from patch_compass.cli import main


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.stdout.strip()


class CliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name) / "repo"
        self.repo.mkdir()
        git(self.repo, "init", "-b", "main")
        git(self.repo, "config", "user.name", "Patch Compass Test")
        git(self.repo, "config", "user.email", "patch-compass@example.invalid")
        (self.repo / "src").mkdir()
        (self.repo / "src" / "app.py").write_text("PRIVATE_SENTINEL = 'do not print'\n", encoding="utf-8")
        git(self.repo, "add", "src/app.py")
        git(self.repo, "commit", "-m", "initial")
        git(self.repo, "switch", "-c", "feature/example")
        (self.repo / "src" / "app.py").write_text("PRIVATE_SENTINEL = 'changed content'\n", encoding="utf-8")
        (self.repo / "new file.txt").write_text("PRIVATE_UNTRACKED_CONTENT\n", encoding="utf-8")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_json_report_lists_paths_but_never_file_contents(self) -> None:
        output = io.StringIO()

        with redirect_stdout(output):
            exit_code = main(["--repo", str(self.repo), "--base", "main", "--format", "json"])

        rendered = output.getvalue()
        report = json.loads(rendered)
        self.assertEqual(0, exit_code)
        self.assertEqual(2, report["changedCount"])
        self.assertIn("src/app.py", rendered)
        self.assertNotIn("PRIVATE_SENTINEL", rendered)
        self.assertNotIn("PRIVATE_UNTRACKED_CONTENT", rendered)

    def test_scan_does_not_change_repository_status(self) -> None:
        before = git(self.repo, "status", "--porcelain", "-z")
        with redirect_stdout(io.StringIO()):
            exit_code = main(["--repo", str(self.repo), "--base", "main"])
        after = git(self.repo, "status", "--porcelain", "-z")

        self.assertEqual(0, exit_code)
        self.assertEqual(before, after)

    def test_non_repository_returns_operational_error(self) -> None:
        empty = Path(self.temp.name) / "empty"
        empty.mkdir()
        error_output = io.StringIO()

        with redirect_stderr(error_output):
            exit_code = main(["--repo", str(empty), "--base", "main"])

        self.assertEqual(1, exit_code)
        self.assertIn("patch-compass:", error_output.getvalue())
        self.assertNotIn(str(empty), error_output.getvalue())

    def test_help_is_available(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output), self.assertRaises(SystemExit) as raised:
            main(["--help"])

        self.assertEqual(0, raised.exception.code)
        self.assertIn("--format", output.getvalue())


if __name__ == "__main__":
    unittest.main()
