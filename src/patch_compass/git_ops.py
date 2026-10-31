from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path


class GitError(RuntimeError):
    """A repository lookup or Git operation failed."""


@dataclass(frozen=True)
class ChangedPath:
    path: str
    status: str


@dataclass(frozen=True)
class ChangeSet:
    base_ref: str
    merge_base: str
    paths: list[ChangedPath]


def _decode(value: bytes) -> str:
    return value.decode("utf-8", errors="surrogateescape")


def _run_git(repo: Path, *args: str, allow_failure: bool = False) -> subprocess.CompletedProcess[bytes]:
    environment = os.environ.copy()
    environment["GIT_NO_LAZY_FETCH"] = "1"
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=repo,
            capture_output=True,
            check=False,
            shell=False,
            timeout=20,
            env=environment,
        )
    except FileNotFoundError as exc:
        raise GitError("Git was not found on PATH.") from exc
    except subprocess.TimeoutExpired as exc:
        raise GitError("A Git command timed out after 20 seconds.") from exc
    except OSError as exc:
        raise GitError(f"Could not start Git: {exc}") from exc

    if result.returncode != 0 and not allow_failure:
        detail = _decode(result.stderr or result.stdout).strip()
        detail = detail.replace(str(repo), "<repo>")
        message = f"Git exited with code {result.returncode}"
        if detail:
            message = f"{message}: {detail}"
        raise GitError(message)
    return result


def _resolve_commit(repo: Path, ref: str) -> str | None:
    result = _run_git(
        repo,
        "rev-parse",
        "--verify",
        "--end-of-options",
        f"{ref}^{{commit}}",
        allow_failure=True,
    )
    if result.returncode != 0:
        return None
    return _decode(result.stdout).strip() or None


def _select_base(repo: Path, requested_base: str | None) -> tuple[str, str]:
    if requested_base:
        commit = _resolve_commit(repo, requested_base)
        if commit is None:
            raise GitError(f"Could not resolve base ref {requested_base!r} to a commit.")
        return requested_base, commit

    symbolic = _run_git(
        repo,
        "symbolic-ref",
        "--quiet",
        "--short",
        "refs/remotes/origin/HEAD",
        allow_failure=True,
    )
    if symbolic.returncode == 0:
        origin_head = _decode(symbolic.stdout).strip()
        commit = _resolve_commit(repo, origin_head)
        if commit:
            return origin_head, commit

    for candidate in ("main", "master"):
        commit = _resolve_commit(repo, candidate)
        if commit:
            return candidate, commit

    raise GitError("Could not find origin/HEAD or a local main/master branch; choose one with --base.")


def _filter_disabling_args(repo: Path) -> list[str]:
    result = _run_git(
        repo,
        "config",
        "--name-only",
        "--get-regexp",
        r"^filter\..*\.(clean|process)$",
        allow_failure=True,
    )
    if result.returncode == 1:
        return []
    if result.returncode != 0:
        raise GitError("Could not inspect configured Git filters.")

    drivers: set[str] = set()
    for key in _decode(result.stdout).splitlines():
        lowered = key.casefold()
        if lowered.endswith(".clean"):
            suffix = ".clean"
        elif lowered.endswith(".process"):
            suffix = ".process"
        else:
            raise GitError("Could not safely disable a configured Git filter driver.")
        if not lowered.startswith("filter."):
            raise GitError("Could not safely disable a configured Git filter driver.")
        driver = key[len("filter.") : -len(suffix)]
        unsupported_name = any(
            not (character.isascii() and (character.isalnum() or character in "_.-"))
            for character in driver
        )
        if not driver or unsupported_name:
            raise GitError("Cannot safely disable a configured Git filter driver; check its name and Git config.")
        drivers.add(driver)

    args: list[str] = []
    for driver in sorted(drivers, key=lambda name: (name.casefold(), name)):
        args.extend(("-c", f"filter.{driver}.clean=", "-c", f"filter.{driver}.process="))
    return args


def _ensure_not_partial_clone(repo: Path) -> None:
    partial_clone = _run_git(
        repo,
        "config",
        "--get-regexp",
        r"^extensions\.partialclone$",
        allow_failure=True,
    )
    if partial_clone.returncode == 0:
        raise GitError("Partial clones are not scanned to prevent on-demand object fetches; use a full clone.")
    if partial_clone.returncode != 1:
        raise GitError("Could not verify whether the repository is a partial clone.")

    promisor_remotes = _run_git(
        repo,
        "config",
        "--bool",
        "--get-regexp",
        r"^remote\..*\.promisor$",
        allow_failure=True,
    )
    if promisor_remotes.returncode == 1:
        return
    if promisor_remotes.returncode != 0:
        raise GitError("Could not verify whether the repository has promisor remotes.")

    for line in _decode(promisor_remotes.stdout).splitlines():
        fields = line.rsplit(None, 1)
        if len(fields) != 2:
            raise GitError("Could not verify whether the repository has promisor remotes.")
        if fields[1].casefold() == "true":
            raise GitError("Partial clones are not scanned to prevent on-demand object fetches; use a full clone.")


def _nul_fields(data: bytes) -> list[bytes]:
    fields = data.split(b"\0")
    if fields and fields[-1] == b"":
        fields.pop()
    return fields


def parse_name_status_output(data: bytes) -> list[ChangedPath]:
    """Parse `git diff --name-status -z` output without splitting filenames."""
    fields = _nul_fields(data)
    changes: list[ChangedPath] = []
    index = 0
    while index < len(fields):
        status = _decode(fields[index])
        index += 1
        if status.startswith("R") or status.startswith("C"):
            if index + 1 >= len(fields):
                raise GitError("Git returned an incomplete rename/copy record.")
            old_path = _decode(fields[index])
            new_path = _decode(fields[index + 1])
            index += 2
            if status.startswith("R"):
                changes.append(ChangedPath(old_path, "D"))
            changes.append(ChangedPath(new_path, "A"))
            continue

        if index >= len(fields):
            raise GitError("Git returned an incomplete changed-path record.")
        changes.append(ChangedPath(_decode(fields[index]), status))
        index += 1
    return changes


def collect_changes(repo: Path, requested_base: str | None) -> ChangeSet:
    """Collect tracked working-tree changes and non-ignored untracked paths."""
    candidate = repo.expanduser().resolve()
    if not candidate.exists():
        raise GitError("The requested repository path does not exist.")

    root_result = _run_git(candidate, "rev-parse", "--show-toplevel")
    root = Path(_decode(root_result.stdout).strip()).resolve()
    _ensure_not_partial_clone(root)
    base_ref, base_commit = _select_base(root, requested_base)
    merge_result = _run_git(root, "merge-base", base_commit, "HEAD")
    merge_base = _decode(merge_result.stdout).strip()

    tracked_result = _run_git(
        root,
        *_filter_disabling_args(root),
        "diff",
        "--name-status",
        "-z",
        "--no-renames",
        "--no-ext-diff",
        "--no-textconv",
        merge_base,
        "--",
    )
    changes = parse_name_status_output(tracked_result.stdout)
    known_paths = {entry.path for entry in changes}

    untracked_result = _run_git(root, "ls-files", "--others", "--exclude-standard", "-z")
    for raw_path in _nul_fields(untracked_result.stdout):
        path = _decode(raw_path)
        if path not in known_paths:
            changes.append(ChangedPath(path, "A"))
            known_paths.add(path)

    changes.sort(key=lambda entry: (entry.path.casefold(), entry.path, entry.status))
    return ChangeSet(base_ref=base_ref, merge_base=merge_base, paths=changes)
