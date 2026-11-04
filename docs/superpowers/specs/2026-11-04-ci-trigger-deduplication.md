# Windows CI trigger deduplication

Research: [Windows CI investigation](../../research/2026-11-04-windows-ci.md), Beads `tt-3d8`.

The user authorized independently accepted CI research followed by Beads optimization tasks and execution without another continue. This first bounded change removes overlapping triggers; it does not shorten or remove tests.

## Chosen design

Keep `.github/workflows/cli.yml` named `Portable CLI`, the `unittest (windows-latest)` check and the full `python -m unittest discover -s tests -v` command. Trigger it on `pull_request` only, preserving default proposed-merge checkout. Add concurrency keyed by workflow and PR number, cancelling only superseded runs of the same PR. No push trigger means branch pushes and main pushes no longer duplicate these checks.

Keep `.github/workflows/postmerge.yml` unchanged: merged PR events on main check out the exact merge SHA, run the full suite and publish the existing Windows merge-event artifact. This is the single full exact-main verification for this PR-based integration route. Independent main source acceptance remains separate. Do not cancel postmerge runs, change check names, protection, permissions, artifact schema or acceptance status publication.

Direct pushes to main and merge queues are outside this PR-based route. Do not describe them as covered or enable them implicitly. If integration later permits them, design an explicit fallback and event identity first. Existing main-push and postmerge CI requirements describe the old duplicate arrangement; after this change exact-main CI is the unchanged postmerge job, not an additional absent push run.

## Alternatives considered

- Retain both triggers and suppress branch pushes with an API lookup: more permission/network/failure modes without benefit for the authorized PR-only integration process.
- Remove postmerge and retain main push: loses the existing PR-bound merge-event artifact producer unless redesigned. Rejected for this change.
- Combine docs classification with trigger removal: couples different acceptance semantics. Defer the classifier to a separate Beads task.

## Acceptance

- A branch push launches no `Portable CLI` workflow; PR open/update still invokes its full Windows job on the proposed merge revision.
- Repeated updates to the same PR may cancel the superseded PR run; distinct PRs and main/postmerge do not share that cancellation group.
- A merged PR invokes the unchanged exact-merge full suite and publishes `task-tower-merge-<PR>-windows` with the actual merge SHA.
- No tests/assertions/timeouts are removed, workflow permissions expanded or protections bypassed.
- Fresh independent whole-diff PR review binds actual head/base, real `task-tower/pr-acceptance` is recorded and actual applicable GitHub CI succeeds before merge. After merge verify exact-main postmerge CI/artifact and independent main source acceptance before coordinator closes the optimization Bead.
- Record actual observed run counts and timings; do not claim a per-run test-speed improvement from deduplication.
