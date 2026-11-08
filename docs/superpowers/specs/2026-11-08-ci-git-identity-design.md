# Reduce fresh Git identity query overhead

Date: 2026-11-08
Status: directly approved by the user on 2026-11-08 for implementation through protected main acceptance
Canonical parent: tt-qrk; current actor task-tower-ci-perf-20261108
Base: e1ba2419222b29c1ef82c0fc0df362ea92003e5e

## Intent and measured baseline

Reduce repeated Git process startup in the full Windows runtime suite without
removing tests or weakening any security predicate, observation boundary,
assertion, timeout, CI gate or acceptance gate.

Six real successful full-runtime runs were read through GitHub's API and shard
logs. Queue means job created_at to started_at; run-to-job dependency waiting is
separate. Run wall includes scope and aggregate jobs. Durations are seconds.

| Run | Route | Run wall | Slowest shard job | Slowest test step |
| --- | --- | ---: | ---: | ---: |
| 42410267932 | PR114 | 491 | 445 | 430 |
| 42410948009 | exact-main PR114 | 522 | 480 | 465 |
| 42459101151 | PR116 | 571 | 504 | 487 |
| 42460021483 | exact-main PR116 | 481 | 440 | 421 |
| 42474961228 | PR117 | 521 | 483 | 468 |
| 42476140736 | exact-main PR117 | 551 | 504 | 487 |

Runtime job queues were 1-3 seconds; PR116 scope queue was 6 seconds. Python setup
was 0-1 seconds, shard checkout 6-13 seconds, artifact upload 1-2 seconds. Scope
execution was 14-29 seconds and aggregate execution 17-27 seconds. PR container
smoke ran concurrently for 78-84 seconds and was not the critical path. The
PR114, PR116 and PR117 inventories contain respectively 1078, 1084 and 1092 tests;
they are not a controlled performance comparison.

API head SHA is not actual tested SHA. Checkout logs establish:

| Run | Actual tested SHA |
| --- | --- |
| 42410267932 | b54dd33ddec7384fee2228b47809d00db5852765 |
| 42410948009 | 5b97ab696fecd67682d2909c21066e4c258b5025 |
| 42459101151 | 142d0afab7b63b16748e8978d3a82db13f1d8961 |
| 42460021483 | 308b8992eac8aceb0bca6e8df4e32f5f8aa3d786 |
| 42474961228 | bce8616772685d077ff20986882dde0421fd12f3 |
| 42476140736 | e1ba2419222b29c1ef82c0fc0df362ea92003e5e |

Local Git objects verify identical PR117/main trees
66be2a6dfb994e23f5a0e34090a64473d36bab75 and identical PR116/main trees
2d38018f72edce2d2e2a83917025c65f8620d397. Thus substantial hosted timing variation
exists even for identical source. No speedup is established by these baselines.

At unchanged base, the existing publication intent-order test took 34.526 seconds
in an instrumented local run. It issued 776 pipeline_inputs Git subprocesses,
including 73 separate --show-toplevel and 73 separate --absolute-git-dir queries.
Those two command groups consumed 1.884 and 1.861 seconds respectively. A separate
cProfile execution took 38.895 seconds including profiling overhead. These two
runs are diagnostics, not an optimization comparison.

## Approaches and proposed choice

Coordinator recommendation: combine only the adjacent fresh root and Git-directory
queries in pipeline_inputs._repository with one rev-parse invocation. This removes
one process per call while retaining all later checks. The independent read-only
technical assessment supports this scope. The user approved this design and
implementation through main with all checks on 2026-11-08.

Refreshing scheduling hints is not selected: PR105 already implemented balancing,
and these runs show large whole-runner variation. Batching HEAD into the first
query is rejected because it moves HEAD observation before filesystem validation.
Combining tracked/untracked enumeration is deferred because untagged Git output
has a filename/header ambiguity and needs a separate security parser review.

## Contract and implementation boundary

- Change only the fresh read-only root/Git-directory query in _repository and its
  focused regression tests. Keep HEAD, symbolic-ref and show-ref as separate fresh
  queries at their original positions. No cached identity or shared Git process.
- Preserve every existing path, ancestry, ordinary-file, linked-worktree binding,
  source/hash, branch and refs predicate. Preserve unknown-intent/no-replay behavior.
- Parse literal LF bytes, require exactly two nonempty records and terminal LF,
  then os.fsdecode each path. Never text.splitlines or whitespace-strip path data.
  Preserve previously supported LF-containing POSIX roots or explicitly bound
  policy.git_dir paths through the original separate-query route; do not
  silently restrict the path domain. A bound Git directory may contain LF even
  when its linked worktree root does not.
- Real ordinary and explicitly bound linked worktrees, spaces and Unicode paths
  must work. Nested roots, unbound/wrong Git directory, malformed output, stale
  expected HEAD and branch-bound detached HEAD must fail closed. Unborn HEAD is
  allowed only where the unchanged policy does not require a HEAD.
- A test must mutate HEAD during the filesystem checks and prove rejection by
  the later fresh HEAD read. Existing environment/token stripping and filesystem
  checks remain unchanged.
- No workflow, scheduler/cost, platform, runner, tariff, installation, account,
  authentication, ACL or production database change. No old workers/monitors,
  UI acceptance or legacy-conveyor activation. tt-qrk.4 risk and .5 pause remain.

Git documents both path options in https://git-scm.com/docs/git-rev-parse.
The installed Git 2.45.2.windows.1 was independently checked for ordered output.

## Verification and delivery

After approval, create one narrow canonical child, atomically claim/readback,
write an implementation plan and use TDD. Verify real repository/path/HEAD cases,
then existing checkpoint/publication/security tests and the full CLI suite.
Measure the same existing workload with and without the query change; retain
individual observations and process counts rather than claiming speedup from a
single noisy sample. Run full real PR and exact-main CI with authentic artifacts,
full discovered inventory, exact-once selections and fail-closed aggregation.
Report actual queue, critical shard/job/test-step and total wall times; label
hosted variability and any absence of confirmed wall-time speedup honestly.

Require fresh independent whole-diff actual head AND base approval, genuine
task-tower/pr-acceptance, all applicable real CI success, mergeability/resolved
conversations and protected expected-head merge, serialized with other main work.
Fresh fetch budget remains 60 seconds and local Git validation 10 seconds. Require
independent exact-main acceptance before canonical child closure/history/readback.
The parent epic stays open while its existing unresolved obligations remain.

The expected saving is one process per identity check (73 processes and roughly
1.9 seconds in the measured local test), not a promised hosted-CI percentage.

## Local implementation measurements

Three alternating pairs executed the existing publication intent-order test in
fresh Python processes. The before process used only the original `_repository`
function from base e1ba241; the after process used the implementation at ad1a926.
All other source and the workload were identical. All six executions succeeded.

| Execution order | Implementation | Seconds | Git calls | Path query calls |
| --- | --- | ---: | ---: | ---: |
| 1 | before | 35.355 | 776 | 146 |
| 2 | after | 33.998 | 703 | 73 |
| 3 | after | 34.933 | 703 | 73 |
| 4 | before | 36.194 | 776 | 146 |
| 5 | before | 35.314 | 776 | 146 |
| 6 | after | 33.441 | 703 | 73 |

Local median fell from 35.355 to 33.998 seconds (approximately 3.8% for this one
workload); paired differences were 1.26-1.87 seconds. This proves the process-count
reduction and records a modest local benefit, not a hosted-CI percentage. Hosted
runner differences can exceed this saving, as the baseline same-tree runs show.

Independent source review subsequently found that the LF fallback's original
whitespace trimming violated the exact-path contract. A failing regression
confirmed it; the correction removes only the terminal LF and retains all path
whitespace. This correction affects the known-LF fallback, not the LF-free path
used by these measurements. Real POSIX LF-path regressions are explicitly skipped
on Windows; a platform-independent mocked boundary regression verifies that the
exact whitespace-bearing path reaches the filesystem guard.
