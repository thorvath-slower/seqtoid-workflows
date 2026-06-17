# Contributing to czid-workflows
CZ ID welcomes contributions and reports of issues encountered using our workflow definitions. When you open a PR, an automated test suite will run
on [GitHub Actions](https://github.com/chanzuckerberg/idseq-workflows/actions), running your workflow on a test adataset and reporting any issues.

# Local CI (`bin/ci-local`)
To validate changes locally before pushing — or when GitHub CI is unavailable —
run `bin/ci-local`. It drives the same `Makefile` targets as the GitHub `wdl-ci`
pipeline (lint → miniwdl check → docker build → step tests → cargo test), **minus
the AWS/ECR push**, so local and CI can't drift. Examples:

```bash
bin/ci-local                  # workflows changed since HEAD^ (else all)
bin/ci-local consensus-genome # a single workflow
LINT_ONLY=1 bin/ci-local      # fast: lint + miniwdl check only (no docker/rust)
```

Prerequisites: Docker, Python (see `.python-version`), and Rust/cargo for the
index-generation tests. No AWS credentials needed. The ECR push, the self-hosted
`wdl-ci-integration` job, and the full benchmarks still require the real CI runner.

# Security
Please disclose security issues responsibly by contacting security@chanzuckerberg.com.
