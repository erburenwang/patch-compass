# Patch Compass Design

## Intent

Patch Compass turns a Git work-in-progress into a short, deterministic review checklist. It helps contributors notice review areas such as tests, dependencies, migrations, API contracts, generated files, and workflow permissions before they open a pull request.

## Goals

- Inspect changes from the merge base of a selected base ref to the current working tree, including non-ignored untracked files.
- Classify paths with documented, deterministic rules and attach plain-language review prompts.
- Report missing companion changes only as review reminders, never as proof of a defect.
- Support terminal, Markdown, and versioned JSON output.
- Run locally with Python 3.11+ and Git 2.30+, without runtime packages or network access.
- Make no repository changes.

## Non-goals and anti-goals

- Do not capture or analyze patch text, infer code correctness, or claim a risk score. Git may read working-tree bytes to determine whether tracked files changed.
- Do not fetch refs, modify the index, create comments, or block a build by default.
- Do not attempt to understand every language-specific build system.

## Approaches

1. **Path-based offline CLI (chosen):** read Git change names and apply a compact rule set. It is fast, reviewable, safe to run locally, and straightforward to test. It can miss behavior changes that path names do not reveal.
2. **Diff-content analyzer:** inspect patch text to infer code behavior. This adds language-specific heuristics, privacy concerns, and false confidence without an AI or compiler model.
3. **Hosted GitHub app/action only:** useful in pull requests but requires repository permissions and does not help during local review.

The local CLI is the product; documentation will show a minimal GitHub Actions job that writes its Markdown report to the step summary.

## Interface

`patch-compass [--repo PATH] [--base REF] [--format text|markdown|json]`

- Default repo: current directory.
- Default base: `origin/HEAD`, then local `main`, then local `master`; fail with a clear error if none resolves.
- Compare the resolved merge base with the current tracked working tree and add non-ignored untracked paths. Renames are reported as removed and added paths.
- Exit `0` when a report is produced, `1` for repository/Git errors, and `2` for invalid arguments.
- JSON has `schemaVersion: 1`, base and merge-base refs, changed path/status entries, category counts, and review prompts.

## Path rules

Rules classify paths into code, tests, dependency manifests/locks, migrations, API contracts, CI/workflows, docs, and generated output. A path can belong to more than one category. Paths are case-insensitive for matching. Report prompts include:

- code without changed tests: check whether changed behavior has regression coverage;
- dependency manifest without a recognized lockfile change: check whether a lockfile should change;
- migration without changed tests: review upgrade, rollback, and data edge cases;
- workflow change: check token permissions, action versions, and secret exposure;
- API/schema change: check compatibility and consumer documentation;
- generated output without source changes: confirm the generated files are reproducible.

Each prompt states the changed-path evidence that triggered it.

## Constraints and privacy

Git is invoked with argument arrays and no shell. Patch Compass consumes only Git's path/status output, disables external diff/textconv helpers and configured clean/process filters, sets `GIT_NO_LAZY_FETCH=1`, and rejects partial clones before resolving refs. Git may read working-tree bytes for change detection. Disabling clean filters can produce extra modified-path entries for files whose working-tree representation normally relies on those filters. The report contains repository-relative paths, statuses, and derived categories only, never diff or file contents. All default behavior is read-only and offline.

## Success criteria

- Unit tests cover categories, companion prompts, JSON stability, and unusual path characters.
- Integration tests use a disposable Git repository to confirm base resolution, tracked diff parsing, and inclusion of untracked files.
- The installed command works outside the source directory.
- GitHub Actions passes on the published default branch.
