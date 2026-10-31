from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from patch_compass.git_ops import (
    ChangedPath,
    GitError,
    _run_git,
    _filter_disabling_args,
    collect_changes,
    parse_name_status_output,
)


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


class GitOpsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        git(self.repo, "init", "-b", "main")
        git(self.repo, "config", "user.name", "Patch Compass Test")
        git(self.repo, "config", "user.email", "patch-compass@example.invalid")
        (self.repo / "src").mkdir()
        (self.repo / "src" / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
        git(self.repo, "add", "src/app.py")
        git(self.repo, "commit", "-m", "initial")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_collects_branch_changes_and_non_ignored_untracked_files(self) -> None:
        git(self.repo, "switch", "-c", "feature/example")
        (self.repo / "src" / "app.py").write_text("VALUE = 2\n", encoding="utf-8")
        git(self.repo, "add", "src/app.py")
        git(self.repo, "commit", "-m", "change implementation")
        (self.repo / "tests").mkdir()
        (self.repo / "tests" / "test_app.py").write_text("def test_app(): pass\n", encoding="utf-8")

        changes = collect_changes(self.repo, None)

        self.assertEqual("main", changes.base_ref)
        self.assertEqual(
            {("M", "src/app.py"), ("A", "tests/test_app.py")},
            {(entry.status, entry.path) for entry in changes.paths},
        )
        self.assertEqual(git(self.repo, "rev-parse", "main"), changes.merge_base)

    def test_explicit_base_is_used(self) -> None:
        git(self.repo, "switch", "-c", "feature/explicit")
        (self.repo / "src" / "app.py").write_text("VALUE = 3\n", encoding="utf-8")

        changes = collect_changes(self.repo, "main")

        self.assertEqual("main", changes.base_ref)
        self.assertEqual([ChangedPath("src/app.py", "M")], changes.paths)

    def test_invalid_base_is_reported_as_git_error(self) -> None:
        with self.assertRaises(GitError):
            collect_changes(self.repo, "missing-base-ref")

    def test_origin_head_takes_precedence_when_present(self) -> None:
        main_commit = git(self.repo, "rev-parse", "main")
        git(self.repo, "update-ref", "refs/remotes/origin/release", main_commit)
        git(self.repo, "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/release")

        changes = collect_changes(self.repo, None)

        self.assertEqual("origin/release", changes.base_ref)

    def test_master_is_used_when_main_is_absent(self) -> None:
        git(self.repo, "branch", "master", "main")
        git(self.repo, "switch", "-c", "feature/master-fallback")
        git(self.repo, "branch", "-D", "main")

        changes = collect_changes(self.repo, None)

        self.assertEqual("master", changes.base_ref)

    def test_name_status_parser_preserves_embedded_tabs_and_newlines(self) -> None:
        changes = parse_name_status_output(b"M\0src/a\tb\n.py\0A\0docs/guide-\xe6\xa0\x91.md\0")

        self.assertEqual(
            [ChangedPath("src/a\tb\n.py", "M"), ChangedPath("docs/guide-树.md", "A")],
            changes,
        )

    def test_collect_changes_does_not_run_case_distinct_clean_filters(self) -> None:
        filter_script = self.repo / ".git" / "filter_probe.py"
        filter_script.write_text(
            "import sys\n"
            "from pathlib import Path\n"
            "Path(__file__).with_name('filter-ran').write_text('ran', encoding='utf-8')\n"
            "sys.stdout.buffer.write(sys.stdin.buffer.read())\n",
            encoding="utf-8",
        )
        filter_command = f'"{Path(sys.executable).as_posix()}" "{filter_script.as_posix()}"'
        git(self.repo, "config", "filter.Probe.clean", filter_command)
        git(self.repo, "config", "filter.probe.clean", filter_command)
        (self.repo / ".gitattributes").write_text(
            "filtered-uppercase.txt filter=Probe\nfiltered-lowercase.txt filter=probe\n",
            encoding="utf-8",
        )
        filtered_paths = [self.repo / "filtered-uppercase.txt", self.repo / "filtered-lowercase.txt"]
        for filtered_path in filtered_paths:
            filtered_path.write_text("base\n", encoding="utf-8")
        git(self.repo, "add", ".gitattributes", "filtered-uppercase.txt", "filtered-lowercase.txt")
        git(self.repo, "commit", "-m", "add filter fixture")

        clean_keys = git(self.repo, "config", "--name-only", "--get-regexp", r"^filter\..*\.clean$").splitlines()
        self.assertIn("filter.Probe.clean", clean_keys)
        self.assertIn("filter.probe.clean", clean_keys)

        marker = self.repo / ".git" / "filter-ran"
        marker.unlink(missing_ok=True)
        for filtered_path in filtered_paths:
            filtered_path.write_text("changed\n", encoding="utf-8")

        changes = collect_changes(self.repo, "main")

        self.assertTrue(
            {ChangedPath("filtered-uppercase.txt", "M"), ChangedPath("filtered-lowercase.txt", "M")}.issubset(
                set(changes.paths)
            )
        )
        self.assertFalse(marker.exists(), "diff must not invoke configured clean filters")

    def test_filter_disabling_args_cover_clean_and_process_for_case_distinct_drivers(self) -> None:
        config_result = subprocess.CompletedProcess(
            args=["git", "config"],
            returncode=0,
            stdout=b"filter.Probe.clean\nfilter.probe.process\n",
            stderr=b"",
        )
        with patch("patch_compass.git_ops._run_git", return_value=config_result):
            args = _filter_disabling_args(self.repo)

        self.assertIn("filter.Probe.clean=", args)
        self.assertIn("filter.Probe.process=", args)
        self.assertIn("filter.probe.clean=", args)
        self.assertIn("filter.probe.process=", args)

    def test_partial_clone_metadata_is_rejected_before_object_resolution(self) -> None:
        for key, value in (
            ("extensions.partialClone", "origin"),
            ("remote.fixture.promisor", "true"),
        ):
            with self.subTest(key=key):
                git(self.repo, "config", key, value)
                with patch("patch_compass.git_ops._run_git", wraps=_run_git) as run_git:
                    with self.assertRaisesRegex(GitError, "Partial clones are not scanned"):
                        collect_changes(self.repo, "main")
                commands = [call.args[1] for call in run_git.call_args_list if len(call.args) > 1]
                self.assertNotIn("merge-base", commands)
                git(self.repo, "config", "--unset", key)

    def test_git_calls_disable_lazy_fetch_even_if_environment_allows_it(self) -> None:
        result = subprocess.CompletedProcess(
            args=["git", "version"],
            returncode=0,
            stdout=b"git version 2.52.0\n",
            stderr=b"",
        )
        with patch("patch_compass.git_ops.subprocess.run", return_value=result) as run_git:
            with patch.dict(os.environ, {"GIT_NO_LAZY_FETCH": "0"}):
                _run_git(self.repo, "version")

        self.assertEqual("1", run_git.call_args.kwargs["env"]["GIT_NO_LAZY_FETCH"])


if __name__ == "__main__":
    unittest.main()
