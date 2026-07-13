# Maintenance register — seqtoid-workflows

**Purpose.** A complete inventory of what in this repo is kept current automatically
(SSOT version files + Renovate) versus what a human must maintain by hand, with the
exact file path and in-file location of each. If it's in the "human-maintained" table,
nothing will remind you — so this list is how we avoid silently drifting.

> ⚠️ **Renovate is configured (`renovate.json`) but the GitHub app
> is not enabled yet.** No Renovate branch / Dependency Dashboard / PR
> history in this fork. Until the app is on, *everything* below is effectively
> human-maintained. The "Automated" table describes what Renovate *will* cover once on.

> ℹ️ **No WDL Renovate manager (and none is needed).** Every WDL task uses
> `docker: docker_image_id` (a workflow input variable), not a hardcoded image tag, so
> there is nothing in the `.wdl` files for Renovate to match. The real image contents are
> the per-workflow `Dockerfile`s, and the tool versions inside them are fetched via
> `curl`/`git clone` URLs that Renovate's `dockerfile` manager does **not** parse — all in
> table A.

## A. Human-maintained (Renovate / SSOT cannot track these)

| # | Item | Where (path → location in file) | Why it's manual | How to update |
|---|------|--------------------------------|-----------------|---------------|
| A1 | WDL task runtime image | `workflows/*/*.wdl` → every `runtime { … docker: docker_image_id }` | Image is a passed-in input variable, not a tag — Renovate has nothing to match | No change in the WDL; update the corresponding `Dockerfile` (rows below) |
| A2 | Tool versions baked into Dockerfiles via `curl`/`wget` release URLs | `workflows/*/Dockerfile` → `RUN curl …/releases/download/vX.Y.Z/…` (e.g. `amr/Dockerfile:11` diamond, `:13` samtools, `:14` bwa, `:35` seqkit; `consensus-genome/Dockerfile:61` blast; `legacy-host-filter/Dockerfile:74` czid-dedup, `:101` picard, `:130` kallisto; `short-read-mngs/Dockerfile`; `long-read-mngs/Dockerfile`; `index-generation/Dockerfile:28`; `phylotree-ng/Dockerfile:34`; `host-genome-generation/Dockerfile:9`) | Versions hardcoded inside download URLs; Renovate's dockerfile manager reads only `FROM`, not `curl` targets | Bump the version in the URL; rebuild + run step tests (`bin/ci-local <workflow>`) |
| A3 | Tool versions pinned via Dockerfile `ARG`/`ENV` | `amr/Dockerfile:31` (`SEQFU_VER`), `legacy-host-filter/Dockerfile:4` & `short-read-mngs/Dockerfile:28` (`MINIWDL_VERSION`), `short-read-mngs/Dockerfile:6` & `lib/s3quilt/Dockerfile:5` (`GO_VERSION`), `index-generation/Dockerfile:54` (`RUST_VERSION`, rustup at `:65`) | `ARG`/`ENV` build args are not version-tracked by Renovate | Edit the `ARG`/`ENV` value; rebuild |
| A4 | Tools built from `git clone` of forks (no tag/SHA pin) | `diamond/Dockerfile:9` (`git clone …morsecodist/diamond`), `minimap2/Dockerfile:9` (`…mlin/minimap2-scatter`) | Cloned at build time from `HEAD` of a fork; not a package Renovate sees | Pin/track the upstream fork manually (fork-and-pin candidates) |
| A5 | Pinned reference-data S3 paths (dated snapshots) | `short-read-mngs/non_host_alignment.wdl` / `postprocess.wdl` / `experimental.wdl` (`s3://czid-public-references/.../2021-01-22/…`); `amr/run.wdl` (`card/2023-05-22/…`); `consensus-genome/run.wdl`; `short-read-mngs/host_filter_defaults.yml` | Hardcoded bucket + dated reference DB versions; pipeline-science decision, no updater | Update the date/path by hand when reference data is regenerated; coordinate with index-generation |
| A6 | Reference data baked into images | `amr/Dockerfile:39` (`curl …czid-public-references…/card/2023-05-22/card.json`) | Bucket + dated path baked into Dockerfile | Bump path; rebuild |
| A7 | Hardcoded S3 buckets / AWS asset URLs | `short-read-mngs/Dockerfile` (ecr-credential-helper, gsnap, RAPSearch2 asset URLs); `legacy-host-filter/Dockerfile`; `short-read-mngs/auto_benchmark/run_dev.py` (`idseq-samples-development`) | Bucket names / legacy asset URLs are infra constants | Manual; change only with infra coordination |
| A8 | `requirements-dev.txt` (root) pins | `requirements-dev.txt` (whole file — miniwdl, pytest, boto3, biopython, …) | Pinned deliberately. Renovate `pip_requirements` *would* group-bump these once enabled, but they are held manual — confirm policy before letting Renovate touch them | Bump by hand; run `bin/ci-local` |
| A9 | Per-workflow `requirements*.txt` pins | `workflows/amr/requirements.txt`, `workflows/phylotree-ng/requirements.txt`, `workflows/index-generation/requirements.txt`, `workflows/bulk-download/requirements.txt`, `workflows/benchmark/requirements-dev.txt` | Same as A8 — Renovate `pip_requirements` *would* cover these once on; today nothing tracks them | Bump by hand until Renovate is enabled |
| A10 | Rust crate + toolchain pins | `workflows/index-generation/ncbi-compress/Cargo.toml` → `[dependencies]` + `[toolchain] channel = "nightly"`; Dockerfile `RUST_VERSION=1.70.0` | Renovate `cargo` *would* cover `[dependencies]`; the `nightly` channel + Dockerfile `RUST_VERSION` are manual regardless and can drift from each other | Bump crate versions / toolchain by hand |
| A11 | Third-party Actions pinned to specific versions | `.github/workflows/short-read-mngs-viral-benchmarks.yml:15` & `wdl-ci-integration.yml:15` (`styfle/cancel-workflow-action@0.9.0`) | Renovate github-actions *would* track these once on; until then manual | Bump tag by hand |
| A12 | Self-hosted runner label | `.github/workflows/wdl-ci-integration.yml` (`runs-on: [self-hosted, idseq-dev]`) | Infra-specific runner identifier; no updater | Manual; coordinate with infra |
| A13 | Release / deployment plumbing | `scripts/release.sh` (git-tag scheme `WORKFLOW-vMAJOR.MINOR.PATCH`, `gh api …/idseq/deployments`) | Bespoke CI logic + hardcoded `idseq` deployment target | Manual |
| A14 | `bin/ci-local` harness logic | `bin/ci-local` (whole file) | Bespoke local-CI script mirroring `wdl-ci.yml`; kept in sync by hand | Update when CI or Makefile targets change |

## B. Automated — SSOT version files + Renovate
*(All rows below are pending the Renovate GitHub app being enabled — see the banner.)*

| # | Item | Where (path → location in file) | Maintained by |
|---|------|--------------------------------|---------------|
| B1 | Python runtime version (SSOT) | `.python-version` → `3.10` | SSOT version file; consumed by `bin/ci-local` + `Makefile`. (No Renovate manager reads it — human-bumped, consumed everywhere) |
| B2 | Dockerfile base images (`FROM`) | `workflows/*/Dockerfile` `FROM` (e.g. `benchmark/Dockerfile` `quay.io/jupyter/scipy-notebook@sha256:…`; the many `FROM ubuntu:18.04/20.04/22.04`) | Renovate `dockerfile` manager → "docker base images" group; `pinDigests:true` will add `@sha256` to the currently-unpinned `ubuntu` bases |
| B3 | Python pip dependencies | `requirements-dev.txt`, `workflows/*/requirements*.txt` | Renovate `pip_requirements` → "pip deps" group. *Overlaps A8/A9 — root `requirements-dev.txt` was hand-pinned; confirm before auto-bumping* |
| B4 | Rust (Cargo) dependencies | `workflows/index-generation/ncbi-compress/Cargo.toml` → `[dependencies]` | Renovate `cargo` → "cargo deps" group |
| B5 | First-party GitHub Actions `uses:` | `.github/workflows/*.yml` (`actions/checkout@v6`, `actions/cache@v4`, `upload/download-artifact@v4`, `aws-actions/configure-aws-credentials@v4`, `docker/login-action@v4`) | Renovate `github-actions` → "github actions" group |
| B6 | Security/vulnerability alerts | repo-wide deps | Renovate `vulnerabilityAlerts.enabled: true` |

## When you add something, update the register

Adding a new workflow, Dockerfile tool, reference-DB path, S3 bucket, or CI action? Add a
row here. If a human has to remember to bump it, it belongs in **table A**. If
`renovate.json` (or a future custom manager) covers it, put it in **table B** with the
manager named.
