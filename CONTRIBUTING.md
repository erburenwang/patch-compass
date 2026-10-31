# Contributing

Patch Compass is a Python 3.11+ CLI with no runtime dependencies. Its Git scan is local and read-only.

## Local checks

```sh
python -m pip install -e .
python -m unittest discover -s tests -v
python -m compileall -q src tests
patch-compass --help
```

When changing path rules, add a test with a representative path and a literal expected category or prompt. Keep output deterministic and avoid reading file contents.

## Change guidelines

- Keep the scan read-only and offline.
- Do not turn review reminders into blocking risk scores.
- Preserve the JSON schema version or document a version change.
- Invoke Git with argument arrays and `shell=False`.
