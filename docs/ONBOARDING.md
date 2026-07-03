# seqtoid-workflows — Onboarding Guide

A current-state, junior-engineer-friendly tour of this repository. It describes
what is **actually in the repo today** — the layout, how images are built and
tested, and the day-to-day workflow for making a change. Part of the
documentation epic (#394); tracked by #399.

> **Naming note.** The platform is being renamed to **seqtoid**. This repo already
> uses the `seqtoid-*` convention in prose, but many functional/external
> identifiers are still `czid-*` — Docker image names (`czid-<workflow>`), the
> `ghcr.io/chanzuckerberg/czid-workflows/...` public images, and various URLs.
> Those are load-bearing (they resolve to live resources) and are kept as-is.

---

## 1. Overview

This repository holds the **WDL workflow definitions** for the seqtoid
bioinformatics platform (the metagenomic / pathogen-identification pipelines) and
the **Docker images** those workflows run in.

- Pipelines are written in [WDL](https://openwdl.org/) (Workflow Description
  Language) and executed with [`miniwdl`](https://github.com/chanzuckerberg/miniwdl)
  locally and via **SWIPE** on AWS in production.
- Each workflow is a directory under `workflows/` containing one or more `.wdl`
  files plus a `Dockerfile` that defines the runtime image the WDL tasks execute
  in.
- CI builds each changed workflow's image, pushes it to a registry (ECR for the
  private/self-hosted pipeline, ghcr.io for the public one), and runs the
  workflow's **miniwdl step tests** against that freshly-built image.

The main production workflows are:

| Workflow | Purpose |
| --- | --- |
| `short-read-mngs` | Illumina metagenomic NGS: host filtering → non-host alignment (NT/NR) → post-processing. The flagship pipeline. |
| `long-read-mngs` | Nanopore metagenomic NGS. |
| `consensus-genome` | Build consensus genomes (Illumina + Nanopore; SARS-CoV-2 and general viral). |
| `amr` | Antimicrobial-resistance gene detection (RGI/CARD). |
| `phylotree-ng` | Phylogenetic tree construction. |

Additional / supporting workflows in `workflows/`: `diamond`, `minimap2`,
`bulk-download`, `host-genome-generation`, `index-generation` (NCBI index build;
includes a Rust `ncbi-compress` crate), `legacy-host-filter`, and `benchmark`
(the benchmarking harness, not a production pipeline).

---

## 2. Repo layout

```
seqtoid-workflows/
├── workflows/               # one directory per pipeline (see §2.1)
│   ├── short-read-mngs/
│   ├── consensus-genome/
│   ├── amr/
│   ├── long-read-mngs/
│   ├── phylotree-ng/
│   ├── index-generation/    # + Rust ncbi-compress crate
│   ├── benchmark/           # benchmarking harness (not a prod pipeline)
│   └── ...
├── lib/                     # shared code baked into images via the docker build
│   ├── idseq-dag/           # vendored DAG library (short-read/long-read/legacy-host-filter)
│   ├── idseq_utils/
│   └── s3quilt/
├── scripts/
│   ├── docker-build.sh      # the single image-build entrypoint
│   ├── diff-workflows.sh    # which workflows changed vs HEAD^ (drives CI matrix)
│   ├── release.sh           # tag + trigger a workflow release/deploy
│   ├── compare-outputs.py
│   └── run-local-benchmark.py
├── .github/workflows/       # CI/CD (see §4)
├── bin/ci-local             # run the CI pipeline locally (no AWS)
├── Makefile                 # build / pull / run / test targets (see §3, §5)
├── requirements-dev.txt     # miniwdl + test tooling
├── .flake8                  # python lint config
├── CONTRIBUTING.md          # local CI notes
├── MAINTENANCE.md           # dependency / maintenance register
└── RunningCZIDWorkflowsOnARMMacs.md   # ARM-Mac (M-series) setup
```

### 2.1 Inside a workflow directory

A workflow directory (`workflows/<name>/`) typically contains:

- **`*.wdl`** — the workflow definition(s). Most workflows have a single
  `run.wdl`. Some are multi-file:
  - `short-read-mngs` has `local_driver.wdl` (the local entrypoint) plus stage
    files `host_filter.wdl`, `non_host_alignment.wdl`, `postprocess.wdl`,
    `experimental.wdl`.
- **`Dockerfile`** — defines the runtime image the WDL tasks run in. Built with
  the `lib/` directory available as a build context named `lib` (see §3).
- **`test/`** — miniwdl **step tests** plus small fixture inputs (e.g.
  `local_test.yml`, small `.fastq.gz` files). This is what `make test-<name>`
  runs.
- **`integration_test/`** *(some workflows)* — larger miniwdl integration tests,
  run by the separate self-hosted integration job.
- **`manifest.yml`** *(some workflows, e.g. consensus-genome)* — declares the
  workflow's entity/raw inputs, input/output loaders, and mapped outputs (how the
  platform wires the workflow into the app).
- **`README.md`** — per-workflow notes.

---

## 3. How images are built & pushed

**Everything goes through one script:** `scripts/docker-build.sh`. It is a thin
wrapper around `docker buildx`:

```bash
docker buildx build --platform linux/amd64 --build-context lib=lib "$@"
```

Two things to note:

- **`--platform linux/amd64`** — images are always amd64. On an ARM Mac (M-series)
  this cross-builds via emulation; see `RunningCZIDWorkflowsOnARMMacs.md`.
- **`--build-context lib=lib`** — the top-level `lib/` directory is exposed to the
  Dockerfile as a named build context, so a workflow's `Dockerfile` can
  `COPY --from=lib ...` the shared libraries (idseq-dag, idseq_utils, s3quilt).
  This is why changing `lib/` can require rebuilding several workflow images.

You rarely call the script directly — use the `Makefile`:

```bash
export WORKFLOW=consensus-genome
make build       # ./scripts/docker-build.sh workflows/$WORKFLOW -t czid-$WORKFLOW
make rebuild     # force a rebuild (needed after lib/ changes)
make pull        # faster: pull the prebuilt public image instead of building
```

`make build` tags the image locally as `czid-<workflow>`. `make pull` pulls
`ghcr.io/chanzuckerberg/czid-workflows/czid-<workflow>-public:<VERSION>` and
retags it `czid-<workflow>`.

### Where CI pushes images

There are **two** build-and-push CI paths:

1. **`wdl-ci.yml`** (the main pipeline) — builds each changed workflow, pushes it
   to **ECR** in the CI account, then runs step tests against that pushed tag. The
   image URI is `<CI_ACCOUNT_ID>.dkr.ecr.<region>/<workflow>`; on the `main`
   branch it also pushes a `:latest` tag. Auth is via OIDC role assumption
   (`vars.CI_ACCOUNT_ID` / `vars.GHA_ROLE`, CZID-40) — no long-lived keys.
2. **`wdl-ci-integration.yml`** (self-hosted integration) — builds to
   **ghcr.io** (`ghcr.io/<repo>/czid-<workflow>-public`). **Note:** in this
   integration workflow the `docker push` lines are currently commented out
   ("don't push while testing") — it builds and runs integration tests but does
   not publish.

Image tags are derived from `git describe --long --tags --always --dirty`.

---

## 4. How workflows are tested

### 4.1 miniwdl step tests (the core gate)

The primary test type is the **miniwdl step test** under `workflows/<name>/test/`.
Each workflow is tested by:

```bash
make test-<workflow>     # e.g. make test-consensus-genome
```

which runs `pytest` over that workflow's `test/` directory. Tests build/pull the
image, run the WDL (or individual tasks) via miniwdl against small fixtures, and
assert on outputs. `make test` runs the step tests for **all** workflows.

`index-generation` additionally has Rust tests: `make cargo-test-index-generation`
(and CI job `index-generation-cargo-test.yml`).

### 4.2 The CI gates (`.github/workflows/`)

| Workflow file | Trigger | What it does |
| --- | --- | --- |
| `wdl-ci.yml` | every push | For each **changed** workflow (via `diff-workflows.sh`): build → push to ECR → `make test-<w>`. This is the main gate. |
| `wdl-ci-integration.yml` | every push | For each changed workflow that has an `integration_test/` dir: build → `make integration-test-<w>` (self-hosted runner; push disabled). |
| `idseq-dag-tests.yml` | PR / push to main / dispatch | Runs the vendored `lib/idseq-dag` core unit suite on Python 3.12 (`lib/idseq-dag/run_idseq_dag_tests.sh`). |
| `index-generation-cargo-test.yml` | — | Rust `cargo test` for the `ncbi-compress` crate. |
| `security.yml` | — | Security scanning (trivy / gitleaks per the shared reusable). |
| `actionlint.yml` | PR / push touching `.github/workflows/**` | Lints the workflow YAML + shellcheck on `run:` scripts. Recently added; the shellcheck quoting backlog has been swept to zero. |
| `release_workflows.yml` | manual dispatch | Release + deploy a workflow (gated — see §6.3). |
| `short-read-mngs-viral-benchmarks.yml` / `short-read-mngs-full-benchmarks.yml` | main / dispatch only | Benchmarks (see §5). |

**Only changed workflows are tested.** `scripts/diff-workflows.sh` diffs
`workflows/` against `HEAD^` and emits the changed workflow names; the CI matrix
fans out over that list. As a special case, a change under `lib/` forces
`short-read-mngs` and `long-read-mngs` to re-test (they depend on the vendored
idseq-dag).

### 4.3 What lint is currently DISABLED in cloud CI (#445)

Locally, `make lint` runs `pre-commit` (which includes `miniwdl check`) **and**
`flake8`. **In cloud CI this linting is currently disabled** — the `linters:` job
in `wdl-ci.yml` is commented out (see ticket **#445**). Until that is re-enabled:

- **`miniwdl check` and `flake8` do not gate cloud CI** — a WDL static error or a
  flake8 violation will not fail the GitHub pipeline on its own.
- **Run lint yourself before pushing.** `make lint`, or better, `bin/ci-local`
  (which runs lint + `miniwdl check` + build + step tests locally — see §6.1), or
  the fast `LINT_ONLY=1 bin/ci-local`.

The `actionlint.yml` gate (YAML + shellcheck for the workflow files) **is** active
— that is a separate concern from the disabled WDL/python linters.

---

## 5. Benchmarks (dispatch-only, cost note)

The `benchmark` workflow directory and the two `short-read-mngs-*-benchmarks.yml`
CI files run full-scale accuracy/performance benchmarks against reference samples
(`idseq_bench_3`, `idseq_bench_5`) and render a Jupyter notebook report comparing
metrics to a reference library.

**These are expensive full-pipeline runs, so they are deliberately NOT run on
every push:**

- **`short-read-mngs-viral-benchmarks.yml`** runs on push to **`main`** only (plus
  manual `workflow_dispatch`), and only when the diff actually touches
  `short-read-mngs`. It builds the image, runs the benchmark samples, harvests
  statistics, executes the notebook, and warns if any metric deviates >1% from the
  reference library.
- **`short-read-mngs-full-benchmarks.yml`** is **`workflow_dispatch` only** — a
  manual button. It doesn't run the benchmark itself; it uses the GitHub API to
  trigger a full-scale run on the `czid-dev` backend for a specified point release
  + NCBI index version.

**Rule of thumb:** don't expect benchmarks to run on your feature branch. If you
need them, trigger the dispatch manually, and be mindful of the cost (they run the
full pipeline and can require very large instances — see the README system
requirements).

---

## 6. How to make a change (the gated-PR flow)

This is a fork (`thorvath-slower/seqtoid-workflows`) of the upstream
`jsims-slower` repo, with the live UCSF push target being `itars`
(IT-Academic-Research-Services). **All work happens on the fork as small,
single-concern, gated PRs. Never merge without review/sign-off.**

### 6.1 Validate locally first

```bash
make python-dependencies     # creates .venv + installs requirements-dev.txt
bin/ci-local                 # run the CI pipeline locally for changed workflows
bin/ci-local consensus-genome  # ...or a single workflow
LINT_ONLY=1 bin/ci-local     # fast: lint + miniwdl check only (no docker/rust)
```

`bin/ci-local` mirrors the `wdl-ci.yml` pipeline **minus the AWS/ECR push**:
lint → `miniwdl check` → docker build → step tests → cargo test. No AWS
credentials needed. Prerequisites: Docker, Python (see `.python-version` = 3.10),
and Rust/cargo (for the index-generation tests).

### 6.2 Open a gated PR

1. Branch off the base branch (e.g. `integration` or `main`) — one concern per
   branch/PR.
2. Push; let `wdl-ci.yml` (build + step tests for the changed workflow) and
   `actionlint.yml` run.
3. Open a **PR** and get review + sign-off. **Do not self-merge** — merges to the
   trunk are gated.

### 6.3 Releasing a workflow (production deploy path)

Releases are a **manual, gated** dispatch of `release_workflows.yml`, which calls
`scripts/release.sh <workflow> <major|minor|patch> "<notes>"`. This both tags a
release **and triggers a deployment**, so it is protected by two gates:

1. a typed-confirmation input (you must type `release`), and
2. the `release` GitHub Environment's required-reviewer protection (human
   approval before it runs).

`release.sh` computes the next `<workflow>-vX.Y.Z` tag from the last matching tag.

---

## 7. Runbook / gotchas

- **Build platform is always `linux/amd64`.** On an M-series Mac use the
  BuildKit/buildx path (not the legacy builder); follow
  `RunningCZIDWorkflowsOnARMMacs.md`. Expect slow emulated builds.
- **Changing `lib/` means rebuilding dependents.** `lib/` is injected as the
  `lib` build context. After editing anything under `lib/`, `make rebuild` the
  affected workflow(s); CI auto-retests `short-read-mngs` and `long-read-mngs` on
  any `lib/` diff.
- **Cloud CI does not lint WDL/python right now (#445).** `miniwdl check` and
  `flake8` won't fail the GitHub pipeline — run `make lint` / `bin/ci-local`
  yourself. Don't assume a green cloud run means the WDL is statically valid.
- **CI only tests *changed* workflows.** If your change should trigger a
  workflow's tests but doesn't, check `scripts/diff-workflows.sh` (it diffs vs
  `HEAD^`). Squashed/rebased history can affect what's seen as "changed."
- **`short-read-mngs` is the multi-file special case.** Its local entrypoint is
  `local_driver.wdl`, not `run.wdl`; `make run`/`make check` special-case it.
- **Two registries, two images.** The private CI pipeline uses ECR
  (`czid-<workflow>`); the public images are on ghcr.io
  (`czid-<workflow>-public`). `make pull` grabs the public one.
- **`make pull` is faster but may be stale.** Use it to run quickly; use
  `make build`/`rebuild` when you've changed the Dockerfile, `lib/`, or want the
  exact current code.
- **Benchmarks are cost-gated.** They won't run on feature branches — dispatch
  them manually and mind the expense (§5).
- **First-run inputs.** `make run` defaults its inputs from
  `workflows/<name>/test/local_test.yml` (for `short-read-mngs`,
  `local_test_viral.yml`). Override with `INPUT='-i your.yml'` or
  `EXTRA_INPUTS='key=value ...'`.
- **`make ls`** lists available workflows; **`make help`** lists documented
  targets.

---

## 8. Quick reference

```bash
make ls                         # list workflows
make help                       # list make targets
export WORKFLOW=consensus-genome

make python-dependencies        # .venv + miniwdl/test deps
make pull                       # fast: pull prebuilt public image
make build                      # build the image locally (amd64)
make run EXTRA_INPUTS='...'      # run the workflow via miniwdl
make test-consensus-genome      # miniwdl step tests for one workflow
make check                      # miniwdl static check (WORKFLOW=...)
make lint                       # flake8 + pre-commit (miniwdl check)

bin/ci-local [workflow...]       # full local CI (no AWS/ECR push)
LINT_ONLY=1 bin/ci-local         # lint + check only
```

*See also:* `README.md` (quick start), `CONTRIBUTING.md` (local CI),
`MAINTENANCE.md` (dependency register), `RunningCZIDWorkflowsOnARMMacs.md`
(ARM-Mac setup), and each `workflows/<name>/README.md`.
