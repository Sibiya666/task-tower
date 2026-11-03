# Task 2 independent reviewer and process PID seam acceptance

Reviewer: fresh `/root/pr_reviewer_review`, distinct from implementer and coordinator. Reviewed on 2026-11-02 at checkout HEAD `f29a4e7b41ac7fbb92b276fcd49a4c6f58492273`, including the frozen uncommitted Task2 reviewer files and coordinator-owned PID patch. Read repository AGENTS, accepted 2026-11-02 PR-worker design/plan, Task1 R1 review and implementation ledger. No product changes, commits, pushes, installation, model selection or live API writes performed.

**Verdict: ACCEPT the scoped Task2 reviewer implementation and the three-file actual-PID seam. No blocking finding identified in these owned files.** Overall Task2 acceptance is blocked by the independent source review's P1: the final PR reread omits mergeable/mergeable_state consistency, allowing clean-to-blocked drift with snapshot.ready=True. The joint transport test does not establish fresh source readiness; source correction and independent reacceptance are required. This is independent development-stage acceptance, not exact-head/base GitHub PR acceptance and not completion of Issue17. Task3 real authority validation, publication sanitization, durable controller orchestration and installed pilot remain required.

## Frozen content

SHA-256 values below are raw bytes / canonical LF text (UTF-8). A single value means both are identical.

| File | SHA-256 |
| --- | --- |
| task_tower/pr_review.py | `1e5fa9eb45141ef990f4b1d99c8512ac211b3bd65fed094286208ba8cee4cd20` |
| tests/test_pr_review.py | `9a21edfe608f4a11b39dabd84e1d469007092a33c7ffd2e8daa7ea2ded565784` |
| task_tower/pr_source.py (joint seam) | `c6f91e5ba9e5a6fbc5a2fd4d7339d5acf5e3fe209e5ed024b8e412de397bc427` |
| tests/test_pr_source.py (joint seam) | `10a5cefb9a878a46c1838a898a3f5b423fe33dd17ccaba907aa5b68d35eb79ed` |
| task_tower/processes.py | raw `e3c07d5cdff3ad123b92f188fb62d5e03f63c83d024f89ab549ef1058ace52bd`; LF `329bd49d2fb8a155b6eb0002bd43876d003e921081041cfa73f41a09595a890c` |
| task_tower/windows_job.py | raw `9212e216cb52bc55e77ebf0854b86f502b851f74fc26a667b105d4c90085498a`; LF `df5f7de7b6f7e5324070c78422159286222c4b0dfdba2e4ae53d85d8e9b775fe` |
| tests/test_process_pid.py | `29e3359b41231f35c87df29d4c47768fc9545d1399aa38f1f21ebc34845dbb9d` |

All three PID files were independently compared byte-for-byte with sibling `task-tower-github`; all are identical. This verdict explicitly permits coordinator backport of exactly that reviewed seam to Task16, subject to its remaining integration gates. It adds optional-mode pid=None before launch and actual process.pid after successful launch; WindowsJobProcess exposes the CreateProcessW process-information PID. It does not invent IDs or change PRJournal positive-PID validation. Legacy default run_command follows the unchanged legacy function and retains its prior shape.

## Review findings and boundaries

The host request binds current whole nested input and top-level repository/Issue/task/head/base/policy identities, reviewer UUID and attempt. Runner checks the whole actual profile fingerprint separately from validated pinned-instructions fingerprint and rereads request/instructions plus actual pin files after the child. Source uses a host-only runtime `_review_profile`, fresh UUID and exclusive new private directories. Role commands have fixed read-only Codex arguments or explicit trusted custom request/result protocol, no model override/resume/fork. Child environment strips GH_TOKEN/GITHUB_TOKEN case-insensitively.

Strict result parsing rejects duplicate keys, extra fields, wrong types/identities, deep JSON, files over 1 MiB, stale/tampered request and invalid findings. Approval requires actual passed exit 0, confirmed launch/cleanup, positive integer PID, known complete log tails, valid capture counts/hashes, true whole-diff flag, no blocking finding and distinct excluded/prior stage instances. Result/process/request/receipt digests are host-bound data; a model Boolean or imported arbitrary envelope is not process authority. Raw request, argv and private paths are absent from the constructed receipt structure. Model summary/findings remain untrusted prose; Task4 must sanitize them before public publication as specified. The current receipt is private host data, not a ready public report.

The actual source→role test uses real temporary Git commits, bare transport, rename and binary objects and a real child; it proves that full binary diff replaces truncated API patch text, profile hashes agree, actual PID is retained and token variables are absent. Its authority fixture is explicitly host-bound test input: it does not prove Task3 trust or an installed Codex pilot. The read-only Codex argument test is a local executable fixture, not a live model invocation.

## Independent commands and results

Commands used the absolute executable `C:/Users/sibiya666/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe` with ordinary check escalation for actual child processes.

From `task-tower-pr-worker`:

```text
python.exe -m unittest tests.test_pr_review tests.test_pr_source tests.test_process_pid tests.test_processes tests.test_executor_processes tests.test_reviewer -v
Ran 68 tests in 13.984s
OK (skipped=1)
```

From `task-tower-github`:

```text
python.exe -m unittest tests.test_process_pid tests.test_processes tests.test_executor_processes -v
Ran 29 tests in 6.327s
OK (skipped=1)
```

The single skip is unavailable symlink privilege; junction/reparse checks executed successfully. Actual PID tests compare host PID with child's stdout os.getpid(), retain positive PID after timeout/cleanup, require None before cancellation and assert unchanged legacy default shape. Real descendant timeout/normal-exit cleanup and bounded full-stream hash/capture checks pass. No broad full-suite or non-Windows execution is claimed by this review.
