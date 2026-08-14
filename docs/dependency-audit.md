# Dependency and GitHub Actions Audit

This document describes the dependency audit and GitHub Actions supply-chain policy used by CI.

## CI coverage

The `dependency-audit` job runs once on Ubuntu for every pull request and push covered by the Python CI workflow.
It performs the following checks:

1. `uv lock --check` verifies that `uv.lock` matches the project metadata.
2. `uv export --frozen --no-dev --no-emit-project` exports only production dependencies.
3. `pip-audit` checks the exported requirements and fails when a known vulnerability is found.

The existing Linux, macOS, and Windows matrix continues to run lint and tests. It does not repeat the dependency audit.

## Run the audit locally

From the repository root:

```bash
uv sync --python 3.12 --dev
uv lock --check
uv export --frozen \
  --no-dev \
  --no-emit-project \
  --format requirements.txt \
  --output-file .venv/zivo-production-requirements.txt
uv run --locked --no-sync pip-audit \
  --no-deps \
  --disable-pip \
  --requirement .venv/zivo-production-requirements.txt
```

The generated requirements file is under `.venv/`, which is not committed.

License attribution for production runtime dependencies is kept in
`NOTICE.txt`. The wheel declares `pypdf`, `send2trash`, and `textual` through
`Requires-Dist` and does not bundle their code, so their full license texts are
not duplicated in the zivo wheel. The NOTICE file is regenerated from the
frozen production dependency set with:

```bash
uv run --locked --no-sync python scripts/update_notice.py
```

If a future distribution bundles dependency code, it must include the full
license texts for all bundled dependencies in that distribution.

## Handling findings

When `pip-audit` reports a vulnerability, update the affected production dependency to a fixed version when possible, regenerate `uv.lock`, and rerun the audit. The CI output includes the affected package, advisory, and available fixed version.

Do not bypass the audit with an ignore flag or by removing the dependency from the exported requirements.

## Temporary exceptions

If an upgrade cannot be applied immediately, request a temporary exception in the related issue or pull request. The request must include:

- package name, advisory ID, and affected version range;
- why the fixed version cannot be adopted;
- compensating controls or mitigation;
- an owner and an explicit expiry or review date.

A maintainer must approve the exception. Exceptions are temporary and must be revisited when the dependency or release workflow changes.

## GitHub Actions pinning

Every external `uses:` reference in `.github/workflows/` must use a full 40-character commit SHA. A version or branch label may be retained as an inline comment for reviewability, but it is not used as the executable reference.

If an action cannot be pinned, the pull request must document the technical reason and the exact workflow scope where the mutable reference is allowed. No such exception is currently active.
