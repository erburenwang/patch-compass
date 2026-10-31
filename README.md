# Patch Compass

**Turn a Git diff into a review checklist you can act on.**

[![Checks](https://github.com/erburenwang/patch-compass/actions/workflows/ci.yml/badge.svg)](https://github.com/erburenwang/patch-compass/actions/workflows/ci.yml)

Patch Compass reads changed **paths**, classifies the areas they touch, and creates evidence-linked review prompts. It helps contributors remember the right questions for dependency, migration, API, CI, generated-file, test, and documentation changes.

It is a deterministic review aid, not an automatic code reviewer. Patch Compass only consumes Git's path/status output; it does not capture or analyze patch text, or claim that a change is safe or correct. Git may read working-tree bytes to determine whether tracked files changed. External diff/textconv helpers and configured Git clean/process filters are disabled. In worktrees whose tracked files rely on those filters, disabling the conversion can produce extra modified-path entries. Every Git subprocess disables lazy fetching, and partial clones are rejected before object resolution; use a full clone.

## Install

Install the public GitHub source as a command with [uv](https://docs.astral.sh/uv/guides/tools/):

```sh
uv tool install git+https://github.com/erburenwang/patch-compass.git
```

Or clone and install it with Python:

```sh
git clone https://github.com/erburenwang/patch-compass.git
cd patch-compass
python -m venv .venv
# Windows PowerShell: .\.venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
python -m pip install .
```

Requires Python 3.11+ and Git 2.30+.

## Use

From a feature branch, start with the default text report:

```sh
patch-compass
```

Select the base explicitly or choose another output format:

```sh
patch-compass --base origin/main
patch-compass --base main --format markdown
patch-compass --base origin/main --format json
patch-compass --repo ../another-project --base main
```

When `--base` is omitted, Patch Compass tries `origin/HEAD`, then local `main`, then local `master`. It compares the selected merge base with the tracked working tree and includes non-ignored untracked files. Renames appear as a removed path and an added path.

Patch Compass does not fetch. If remote-tracking refs are stale, refresh them yourself before scanning. It never updates the Git index or changes repository files.

## What the checklist covers

| Changed paths | Review prompt |
| --- | --- |
| Source code without a changed test path | Check regression coverage |
| Dependency manifest without a recognized lockfile | Check whether this project maintains a lockfile |
| Migration without a changed test path | Review upgrade, rollback, and data edge cases |
| CI or workflow file | Review token permissions, action versions, and secret exposure |
| API contract or schema | Check backward compatibility and consumer documentation |
| Generated output without code or API paths | Confirm generated artifacts are reproducible |
| Documentation | Check examples, links, and behavior descriptions |

These are path-based reminders. A detected category does not mean the change is wrong, and no prompt does not mean the change is correct. The rules are intentionally simple and visible in `src/patch_compass/analysis.py`.

## GitHub Actions summary

You can append a Markdown checklist to a pull request workflow summary:

```yaml
name: Review checklist
on: pull_request
permissions:
  contents: read
jobs:
  checklist:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
        with:
          fetch-depth: 0
      - uses: actions/setup-python@v7
        with:
          python-version: "3.12"
      - run: python -m pip install --no-deps .
      - name: Write review checklist
        run: patch-compass --base "${{ github.event.pull_request.base.sha }}" --format markdown >> "$GITHUB_STEP_SUMMARY"
```

## Output and privacy

- `text`, `markdown`, and versioned `json` reports are supported.
- Exit code `0` means a report was produced; `1` means a Git/repository error; invalid arguments use argparse's exit code `2`.
- Reports include repository-relative paths, change statuses, categories, and review prompts. They do not include diff contents or absolute repository paths.
- The scan is local and offline. It does not fetch, run build/test commands, create comments, or modify files. External diff/textconv helpers and configured Git clean/process filters are disabled; partial clones are rejected to prevent on-demand object fetches.

## License

MIT. See [LICENSE](LICENSE).

---

# Patch Compass（简体中文）

**把 Git 改动整理成一份可执行的审阅清单。**

Patch Compass 只消费 Git 返回的改动路径和状态，根据透明的规则标注受影响的区域，并生成带路径证据的审阅提醒。为了判断已跟踪文件是否变化，Git 可能读取工作树字节；工具不接收或分析补丁文本，也不会声称改动安全或正确。它帮助贡献者检查依赖、迁移、API、CI、生成文件、测试和文档等变更。

它是确定性的审阅辅助工具，不会分析 Git 返回的补丁/文件内容，也不会自动判断代码是否安全或正确。外部 diff/textconv 辅助程序及 Git clean/process 过滤器会被禁用。若工作树文件依赖这些转换，禁用转换后可能会多报未实际变化的路径。每条 Git 子进程都会禁用延迟抓取，并在解析对象前拒绝 partial clone；请使用完整克隆。

## 安装

通过 [uv](https://docs.astral.sh/uv/guides/tools/) 从公开 GitHub 仓库安装：

```sh
uv tool install git+https://github.com/erburenwang/patch-compass.git
```

也可以克隆后用 Python 安装：

```sh
git clone https://github.com/erburenwang/patch-compass.git
cd patch-compass
python -m venv .venv
# Windows PowerShell: .\.venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
python -m pip install .
```

需要 Python 3.11 及以上版本和 Git 2.30 及以上版本。

## 使用

在功能分支上运行默认文本报告：

```sh
patch-compass
```

也可以指定基准分支或输出格式：

```sh
patch-compass --base origin/main
patch-compass --base main --format markdown
patch-compass --base origin/main --format json
patch-compass --repo ../another-project --base main
```

省略 `--base` 时，工具依次尝试 `origin/HEAD`、本地 `main` 和本地 `master`。它对比选定 merge base 与当前已跟踪工作树，并纳入未被忽略的未跟踪文件。重命名会显示为一个删除路径和一个新增路径。

工具不会执行 fetch。如果远端跟踪引用可能过期，请在扫描前自行刷新。扫描不会更新 Git 索引或修改仓库文件。

## 清单会提示什么

| 改动路径 | 审阅提醒 |
| --- | --- |
| 源码变化但没有测试路径变化 | 检查回归测试覆盖 |
| 依赖清单变化但没有识别到锁文件 | 检查项目是否需要更新锁文件 |
| 数据迁移变化但没有测试路径变化 | 检查升级、回滚和数据边界 |
| CI 或工作流文件 | 检查令牌权限、Action 版本和密钥暴露 |
| API 合约或 Schema | 检查向后兼容性和消费者文档 |
| 生成产物变化但没有源码/API 路径 | 确认生成过程可复现 |
| 文档变化 | 检查示例、链接和行为描述 |

这些提醒只根据路径规则触发。某个类别不表示改动有问题；没有提醒也不表示改动正确。规则都能在 `src/patch_compass/analysis.py` 中查看。

## GitHub Actions 摘要

可以把 Markdown 清单追加到 Pull Request 工作流摘要中：

```yaml
name: Review checklist
on: pull_request
permissions:
  contents: read
jobs:
  checklist:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
        with:
          fetch-depth: 0
      - uses: actions/setup-python@v7
        with:
          python-version: "3.12"
      - run: python -m pip install --no-deps .
      - name: Write review checklist
        run: patch-compass --base "${{ github.event.pull_request.base.sha }}" --format markdown >> "$GITHUB_STEP_SUMMARY"
```

## 输出与隐私

- 支持 `text`、`markdown` 和带版本号的 `json`。
- 退出码 `0` 表示报告已生成；`1` 表示 Git/仓库操作错误；参数错误由 argparse 返回 `2`。
- 报告只包含仓库相对路径、改动状态、类别和审阅提醒，不含补丁内容或仓库绝对路径。
- 扫描本地离线完成，不 fetch、不运行构建/测试命令、不创建评论，也不修改文件；外部 diff/textconv 辅助程序及 Git clean/process 过滤器会被禁用，并拒绝可能触发按需抓取的 partial clone。

## 许可

MIT，见 [LICENSE](LICENSE)。
