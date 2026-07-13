# Branching + promotion model

How changes move from a laptop to the shared dev environment, and what each branch
means. This mirrors the app model (`thorvath-slower/seqtoid-web` `docs/branching.md`),
adapted for this pipeline/WDL repo: there are no per-PR preview sandboxes, and `main` is
released/deployed via the release workflow, not automatically on push.

> **TL;DR:** Branch off `integration`. Open a small PR back into `integration` -- it runs
> the security + WDL/lint gates. `integration` is the active trunk where reviewed work
> accumulates. On a **weekly cadence** the good-to-go state of `integration` is promoted
> to `main`. `main` is the known-good trunk that gets released to dev (and promoted onward
> to staging/prod). `main` is never edited directly.

---

## The picture

```
  feature/bug/improvement       PR      integration      weekly       main       release (manual dispatch)
  branch off integration  ----------->  (active      ----------->  (known-good  --------------------->  dev
  (cat-NNN-slug)                         trunk)       promotion     trunk)                              |
                                                      (automated)                                       v
                                                                              main --gated--> staging --gated--> prod
```

- **`integration` = the active development trunk.** Feature PRs branch off it and merge
  back into it once green + reviewed. It accumulates reviewed changes between promotions
  and does not release to any environment.
- **`main` = known-good.** The weekly roll-up of `integration`. It is released to dev via
  the release workflow (`workflow_dispatch`) -- a merge to `main` does **not** auto-release.
  From `main`, changes promote onward through the gated staging -> prod chain.
- **feature branches** are where you work: `cat-NNN-short-slug` off `integration`.

---

## The dev inner loop

1. **Branch off `integration`:** `git switch -c cat-NNN-short-slug origin/integration`.
2. **Validate locally first:** `make lint` (miniwdl check over the WDLs + flake8 over the
   Python helpers) green before you push. CI is the final gate, not your dev loop.
3. **Open a small PR into `integration`.** This runs the required security + WDL/lint
   checks + review.
4. **Merge to `integration`** once green + reviewed.

## Promotion

### `integration` -> `main` (weekly, automated)

`.github/workflows/promote-integration-to-main.yml` promotes the green state of
`integration` to `main` on a **weekly cadence** (opens/reuses an `integration -> main`
PR and auto-merges when `main`'s required checks pass). Every change was already reviewed
on its own PR into `integration`, so the roll-up is an aggregation of vetted work.

### Hotfix (expedited promotion)

An urgent fix still flows **through `integration`** (checks + review), then a person
triggers the **same** promotion workflow off-cycle via `workflow_dispatch`. One path,
two triggers (`schedule` + manual); no commit-message suffix.

### `main` -> dev / staging / prod (release)

Releases are **manual** (`workflow_dispatch`) via the release workflow, gated per tier;
prod is never released directly. A promotion to `main` makes a change *eligible* to be
released to dev -- it does not release on its own.

---

## Branch protection (enforced)

On `thorvath-slower/seqtoid-workflows`:

- **`integration`** requires the security + WDL/lint checks, a review, and no force-push /
  no deletion.
- **`main`** takes changes **only** via the `integration -> main` promotion (no direct
  pushes), requires the same checks, and no force-push / no deletion.

---

## Notes

- **End-state:** stand this same model up on the IT-ARS (UCSF) repos so the whole team
  works against that pipeline. The retired `modernization` snapshot branch is no longer
  used.
- `integration` is fast-forwarded to `main` after each promotion so the two do not drift.
