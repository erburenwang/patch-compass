# Patch Compass Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish a tested, offline CLI that converts Git changes into an evidence-linked review checklist.

**Architecture:** `git_ops.py` resolves the repository and change set; `analysis.py` maps paths to categories and prompts; `report.py` renders stable text, Markdown, and JSON; `cli.py` owns arguments and exit codes. Tests use `unittest` and temporary Git repositories.

**Tech Stack:** Python 3.11+, Git 2.30+, Python standard library only.

**Spec:** `docs/superpowers/specs/2026-10-31-patch-compass-design.md`

## Global Constraints

- Do not capture or analyze patch text or make network requests; Git may read working-tree bytes to determine tracked changes. Disable external diff/textconv helpers and configured clean/process filters, set `GIT_NO_LAZY_FETCH=1`, and reject partial clones before object resolution.
- Do not modify the inspected Git repository.
- Keep all Git calls as argument arrays with `shell=False`.
- Exit `0` for a report, `1` for operational errors, and `2` for invalid arguments.
- Missing companion files are review prompts, not failures.

## Review Focus

- Filenames with spaces, tabs, newlines, or non-ASCII characters must survive Git's NUL-delimited output and JSON serialization.
- Added untracked paths must not be omitted or duplicated with tracked changes.
- Missing `origin/HEAD` must produce documented `main`/`master` fallback behavior.
- No-change reports must remain valid and deterministic.
- Refs beginning with `-` must not become Git options.

---

### Task 1: Git change-set reader

**Files:**
- Create: `src/patch_compass/git_ops.py`
- Test: `tests/test_git_ops.py`

**Interfaces:**
- Produces `ChangedPath(path: str, status: str)`, `ChangeSet(base_ref: str, merge_base: str, paths: list[ChangedPath])`, and `collect_changes(repo: Path, requested_base: str | None) -> ChangeSet`.

- [x] Write tests for explicit base, `origin/HEAD`/`main`/`master` selection, tracked modifications, untracked files, and unusual path names.
- [x] Run `python -m unittest tests.test_git_ops -v`; tests must fail before implementation.
- [x] Implement Git calls with NUL-delimited output and `shell=False`.
- [x] Run the focused tests and require all pass.
- [x] Commit `git_ops.py` and `test_git_ops.py` after the focused tests pass.

### Task 2: Path analysis and reports

**Files:**
- Create: `src/patch_compass/analysis.py`, `src/patch_compass/report.py`
- Test: `tests/test_analysis.py`, `tests/test_report.py`

**Interfaces:**
- Consumes `ChangeSet` from Task 1.
- Produces `analyze(changes: ChangeSet) -> dict` and `render_report(report: dict, output_format: str) -> str`.

- [x] Write tests for category rules, evidence-linked prompts, zero-change reports, and JSON schema.
- [x] Run `python -m unittest tests.test_analysis tests.test_report -v`; tests must fail before implementation.
- [x] Implement ordered path rules and stable report serialization.
- [x] Run the focused tests and require all pass.
- [x] Commit `analysis.py`, `report.py`, and their tests after the focused tests pass.

### Task 3: CLI, packaging, and release checks

**Files:**
- Create: `src/patch_compass/cli.py`, `src/patch_compass/__init__.py`, `src/patch_compass/__main__.py`, `pyproject.toml`, `.gitignore`, `.gitattributes`, `.github/workflows/ci.yml`, `README.md`, `LICENSE`, `CONTRIBUTING.md`
- Test: `tests/test_cli.py`

- [x] Write CLI tests for help, JSON and text output, repository immutability, and operational errors; confirm failing first.
- [x] Implement the entry point and packaging metadata with no runtime dependencies.
- [x] Document English and Simplified Chinese usage, limits, exit codes, and a GitHub Actions summary example.
- [x] Run the full unit suite, compile check, package install, CLI smoke checks, and a disposable-repository end-to-end scenario.
- [ ] Commit the verified source, create a public GitHub repository, publish the complete tree, and verify remote tree equality and Actions status.

## Execution choice

Implement inline in the current workspace. The user explicitly requested a completed public GitHub release; do not pause between tasks for another approval.
