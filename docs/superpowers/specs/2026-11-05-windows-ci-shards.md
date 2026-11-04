# Parallel Windows unittest verification

Canonical task: `tt-qrk.3`; research: [measured CI costs](../../research/2026-11-04-windows-ci.md). The user explicitly requested faster checks after duplicate trigger removal. This changes CI scheduling, not archived conveyor behavior, test assertions, process containment or timeout semantics.

## Design

Use four independent `windows-latest` jobs for the full CLI suite in PR and exact-main postmerge workflows. Each job discovers the same standard-library unittest suite, validates discovery, sorts unique test identities, and selects every fourth identity at its zero-based index. Four selections must be disjoint and their union equal the full discovered set. Keep normal unittest setup/cleanup/skip/failure semantics within each selected suite. No threads share test globals or environment. Use explicit Python3.11 in every shard.

The standard-library runner `task_tower/ci_unittest.py` validates integer shard count/index, nonempty discovery, discovery errors, supported suite members and duplicate IDs before executing anything. Discovery failures must fail every shard rather than disappear from a selected partition. It supports read-only inventory (`--list`) and normal execution with failure-propagating exit status. It does not execute task text, load private configuration or modify test source. A manifest records exact discovered and selected identities for diagnosis. The ordinary serial `python -m unittest discover -s tests -v` remains available unchanged.

Retain the discovered TestCase objects, including custom `load_tests` exclusions, rather than reconstruct selected names. Aggregates must compare all four execution manifests: identical full inventory and actual checkout SHA, exactly one index each, prescribed selections, successful execution mode. Missing/duplicate/drifted/inventory-only manifests fail closed. The manifest is additional neutral evidence, never a replacement for actual successful Actions jobs. Include monotonic test durations to guide later balancing; do not claim their scope includes module/class fixture costs.

`Portable CLI` retains stable final check name `unittest (windows-latest)`. That aggregate job runs even after matrix failure and succeeds only when the entire four-shard matrix succeeded. Supersession remains scoped to the same PR. All shards run with `fail-fast: false`, so one failing shard does not erase the other results. No skipped/failed/cancelled shard can become a passing final gate.

Postmerge shards explicitly check out the actual merge SHA. A dependent Windows aggregation/publisher job retains check name `verify-merge (windows-latest, windows)`, exact-source checkout, existing event schema, artifact name and error propagation. It publishes `checks: passed` only after the complete shard matrix succeeds; otherwise it can publish a failed event and must fail itself. It never claims a full pass from skipped runtime tests. Do not change repository protection, permissions, model/account/auth or consumer configuration.

## Tradeoffs and non-goals

More Windows jobs may queue if repository concurrency is limited. This reduces intended wall time, not guaranteed billable minutes or individual test cost. Four is a bounded initial choice by the coordinator; compare actual slowest-shard and total durations with the measured 22–36 minute serial runs. Do not promise a fourfold gain before observing it. Do not add macOS/Linux/WSL, a docs fast path, direct-push/merge-queue support, a new execution daemon, coverage deletion or weaker timing assertions.

## Acceptance

- Partition tests cover exact-once identity coverage, order stability, uneven sizes, invalid bool/noninteger/out-of-range indices/counts, duplicate IDs, empty suite and discovery failures independent of which partition would contain the failure.
- Runner tests prove failed/error/skipped execution semantics, fixture lifecycle and nonzero exit propagation; inventory mode must not execute tests.
- Actual source inventory across four shards equals the ordinary full discovery set exactly once.
- Fresh independent whole-diff head/base PR approval, actual four-shard Windows CI plus stable aggregate success, then expected-head merge only after the prior main barrier is accepted.
- Fresh exact-main materialization, independent main source acceptance, all actual postmerge shards and genuine merge artifact verified before coordinator closure in Beads. Report observed wall time, queue time and limitations honestly.
