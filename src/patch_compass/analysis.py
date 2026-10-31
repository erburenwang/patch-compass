from __future__ import annotations

from collections import Counter
from pathlib import PurePosixPath

from patch_compass.git_ops import ChangeSet


CATEGORY_ORDER = (
    "code",
    "tests",
    "dependencies",
    "lockfiles",
    "migrations",
    "api",
    "ci",
    "docs",
    "generated",
)

_CODE_SUFFIXES = {
    ".c",
    ".cc",
    ".cpp",
    ".cs",
    ".go",
    ".h",
    ".hpp",
    ".java",
    ".js",
    ".jsx",
    ".kt",
    ".kts",
    ".mjs",
    ".cjs",
    ".php",
    ".py",
    ".rb",
    ".rs",
    ".sh",
    ".swift",
    ".ts",
    ".tsx",
    ".ps1",
}

_LOCK_NAMES = {
    "cargo.lock",
    "composer.lock",
    "gemfile.lock",
    "go.sum",
    "package-lock.json",
    "pipfile.lock",
    "poetry.lock",
    "pnpm-lock.yaml",
    "pnpm-lock.yml",
    "uv.lock",
    "yarn.lock",
}

_DEPENDENCY_NAMES = {
    "cargo.toml",
    "composer.json",
    "directory.packages.props",
    "gemfile",
    "go.mod",
    "package.json",
    "pipfile",
    "pom.xml",
    "pyproject.toml",
    "setup.cfg",
    "setup.py",
}

_CI_NAMES = {
    ".gitlab-ci.yml",
    ".travis.yml",
    "azure-pipelines.yml",
    "azure-pipelines.yaml",
    "jenkinsfile",
}

_DOC_NAMES = {"readme", "contributing", "changelog", "license", "security"}


def _normalise_path(path: str) -> tuple[str, list[str]]:
    normalised = path.replace("\\", "/").strip("/")
    parts = [part for part in normalised.split("/") if part and part != "."]
    return "/".join(parts).casefold(), parts


def _is_test_path(path: str, parts: list[str]) -> bool:
    if any(part.casefold() in {"test", "tests", "__tests__", "spec", "specs"} for part in parts[:-1]):
        return True
    name = parts[-1].casefold() if parts else ""
    suffix = PurePosixPath(name).suffix
    return (
        name.startswith("test_")
        or name.endswith(("_test.go", ".test.js", ".test.jsx", ".test.ts", ".test.tsx", ".spec.js", ".spec.ts", ".spec.tsx"))
        or (name.startswith("test.") and suffix in _CODE_SUFFIXES)
    )


def _is_generated(normalised: str, parts: list[str]) -> bool:
    generated_dirs = {"build", "dist", "generated", "node_modules", "vendor", "__generated__"}
    if any(part.casefold() in generated_dirs for part in parts[:-1]):
        return True
    name = parts[-1].casefold() if parts else ""
    return ".generated." in name or ".gen." in name or ".min." in name or normalised.endswith(".min.js")


def classify_path(path: str) -> tuple[str, ...]:
    """Return stable review categories inferred from a repository-relative path."""
    normalised, parts = _normalise_path(path)
    if not parts:
        return ()

    name = parts[-1].casefold()
    extension = PurePosixPath(name).suffix
    categories: set[str] = set()
    is_generated = _is_generated(normalised, parts)
    is_test = _is_test_path(path, parts)

    if is_generated:
        categories.add("generated")
    if is_test:
        categories.add("tests")

    if name in _LOCK_NAMES:
        categories.add("lockfiles")
    elif (
        name in _DEPENDENCY_NAMES
        or name.startswith("requirements") and extension in {".txt", ".in"}
        or name.startswith("constraints") and extension == ".txt"
        or extension in {".csproj", ".fsproj", ".vbproj", ".gradle"}
        or name.endswith(".gradle.kts")
    ):
        categories.add("dependencies")

    if any(part.casefold() in {"migrations", "migration", "migrate"} for part in parts[:-1]):
        categories.add("migrations")
    elif len(parts) >= 2 and parts[-2].casefold() == "versions" and "alembic" in {part.casefold() for part in parts[:-1]}:
        categories.add("migrations")

    api_schema_suffixes = {".avsc", ".gql", ".graphql", ".openapi", ".proto", ".thrift", ".wsdl"}
    if extension in api_schema_suffixes or name.startswith(("openapi.", "swagger.")):
        categories.add("api")
    elif any(part.casefold() in {"openapi", "swagger", "schemas"} for part in parts[:-1]) and extension in {".json", ".yaml", ".yml"}:
        categories.add("api")

    if normalised.startswith((".github/workflows/", ".circleci/", ".buildkite/")) or name in _CI_NAMES:
        categories.add("ci")

    doc_stem = name.split(".", 1)[0]
    if (
        any(part.casefold() in {"doc", "docs", "documentation"} for part in parts[:-1])
        or doc_stem in _DOC_NAMES
        or extension in {".md", ".mdx", ".rst"}
    ):
        categories.add("docs")

    if not is_generated and not is_test and "api" not in categories and "migrations" not in categories:
        if extension in _CODE_SUFFIXES:
            categories.add("code")

    return tuple(category for category in CATEGORY_ORDER if category in categories)


def _prompt(prompt_id: str, title: str, message: str, paths: list[str]) -> dict[str, object]:
    return {
        "id": prompt_id,
        "title": title,
        "message": message,
        "evidencePaths": sorted(paths, key=lambda value: (value.casefold(), value)),
    }


def analyze(changes: ChangeSet) -> dict[str, object]:
    ordered_paths = sorted(changes.paths, key=lambda item: (item.path.casefold(), item.path, item.status))
    change_rows = [
        {"path": item.path, "status": item.status, "categories": list(classify_path(item.path))}
        for item in ordered_paths
    ]
    counts = Counter(category for row in change_rows for category in row["categories"])

    code_paths = [row["path"] for row in change_rows if "code" in row["categories"]]
    test_paths = [row["path"] for row in change_rows if "tests" in row["categories"]]
    dependency_paths = [row["path"] for row in change_rows if "dependencies" in row["categories"]]
    lock_paths = [row["path"] for row in change_rows if "lockfiles" in row["categories"]]
    migration_paths = [row["path"] for row in change_rows if "migrations" in row["categories"]]
    api_paths = [row["path"] for row in change_rows if "api" in row["categories"]]
    ci_paths = [row["path"] for row in change_rows if "ci" in row["categories"]]
    docs_paths = [row["path"] for row in change_rows if "docs" in row["categories"]]
    generated_paths = [row["path"] for row in change_rows if "generated" in row["categories"]]

    prompts: list[dict[str, object]] = []
    if code_paths and not test_paths:
        prompts.append(
            _prompt(
                "test-coverage",
                "Check regression coverage",
                "Source paths changed without a changed test path; check whether the behavior change has regression coverage.",
                code_paths,
            )
        )
    if dependency_paths and not lock_paths:
        prompts.append(
            _prompt(
                "lockfile-review",
                "Check dependency lockfiles",
                "A dependency manifest changed without a recognized lockfile change; check whether this project maintains a lockfile.",
                dependency_paths,
            )
        )
    if migration_paths and not test_paths:
        prompts.append(
            _prompt(
                "migration-coverage",
                "Review migration behavior",
                "A migration changed without a changed test path; review upgrade, rollback, and data edge cases.",
                migration_paths,
            )
        )
    if ci_paths:
        prompts.append(
            _prompt(
                "workflow-security",
                "Review workflow permissions",
                "A CI or workflow file changed; check token permissions, action versions, and secret exposure.",
                ci_paths,
            )
        )
    if api_paths:
        prompts.append(
            _prompt(
                "api-compatibility",
                "Check API compatibility",
                "An API contract or schema changed; check backward compatibility and consumer documentation.",
                api_paths,
            )
        )
    if generated_paths and not code_paths and not api_paths:
        prompts.append(
            _prompt(
                "generated-source",
                "Verify generated output",
                "Generated output changed without a code or API source path; confirm the artifacts are reproducible.",
                generated_paths,
            )
        )
    if docs_paths:
        prompts.append(
            _prompt(
                "documentation-alignment",
                "Check documentation alignment",
                "Documentation changed; confirm examples, links, and behavior descriptions match the implementation.",
                docs_paths,
            )
        )

    return {
        "schemaVersion": 1,
        "tool": "patch-compass",
        "base": {"ref": changes.base_ref, "mergeBase": changes.merge_base},
        "changedCount": len(change_rows),
        "categoryCounts": {category: counts.get(category, 0) for category in CATEGORY_ORDER},
        "changes": change_rows,
        "prompts": prompts,
    }
