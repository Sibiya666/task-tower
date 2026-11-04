# Task 71 local implementation record

Scope: only Task 3 of `docs/superpowers/plans/2026-11-04-shared-conveyor.md`,
starting at `e881fa115c46d1b80bf6157bf749519d504955e3`. Tasks 1/2 from PR70
were not reimplemented. This is an implementation/check record, not a stage
acceptance receipt, real GitHub pilot, main acceptance or task-done assertion.

The new Windows `pipeline` mode hands identity to the existing installation
journal before any shared-worker model launch. The original live claim owner
CAS-binds its selected consumer and actual queued run. Pending identities cannot
launch, and ordinary adapter submissions and legacy terminal claims cannot gain
pipeline authority. The existing stage/process/check/PR consumer remains the
only engine. No role receipts are imported or synthesized. Legacy outcomes,
claim ownership, assignees, unknown restrictions and historical receipts remain.

## Local checks

Runtime: existing bundled Python 3.12.14, native Windows. Installed Superpowers
7.0.0: all 19 request-manifest files matched their SHA-256 pins. Native helpers
used `C:/Program Files/Git/bin/bash.exe`. The shell workspace helper initially
hit ancestor mkdir access restrictions; precreating this plan's ignored scratch
directory with PowerShell allowed `task-start` to run. Installed files and machine
settings were unchanged.

`python -m unittest tests.test_shared_pipeline -v`: 12 tests passed in 45.830s.
They use real Git/SQLite/HTTP fixtures and existing contained role processes.
Coverage includes permanent ownership after restart/assignee removal, lost
admission/final-CAS responses, pending and foreign consumer/run fencing, legacy
result refusal, ordinary submit refusal before journal mutation, strict Windows
policy and identity/plan/path validation. Reviewer replay/relative-path
reproducers and the premature outcome-file regression were observed failing
before their corrections.

The integration test reached local `ready_for_pr` through the existing six
executor/reviewer roles, three approval records and one configured host check,
with seven distinct cleaned instances. Publication was disabled; the fixture
Issue remained open. This is deterministic fixture evidence, not installed LLM
or live GitHub evidence.

The baseline full suite ran 781 tests in 1775.937s: one failure, seven skips.
`test_shared_worker.NativeSharedWorkerTests.test_two_workers_execute_superpowers_tasks_and_refill_without_duplicate`
started all three fixture harnesses, but none completed. A retained focused
reproduction confirmed three 30-second timeouts with process-tree cleanup true.
A bounded direct native helper probe captured `mkdir` permission denial at the
user-directory ancestor, followed by the installed `sdd-workspace` helper's
missing `plan-path` loop. Its three-second timeout also confirmed cleanup.
The original native fixture/Tasks 1/2 behavior was left unchanged; the test was
neither skipped nor relabeled. The final candidate full suite ran 793 tests in
1891.234s: the same one native-fixture failure and seven skips. All 12 new
handoff tests passed within that run. An earlier candidate run likewise had
793 tests, one identical failure and seven skips (1883.097s). No full-suite
success, native acceptance or task completion is claimed.

Local commit is also blocked: `git add` could not create
`repo.git/worktrees/work/index.lock` (Permission denied), and that lock file does
not already exist. No lock was deleted, metadata restriction bypassed, local Git
configuration changed or commit claimed. The full reviewable diff and new files
remain unstaged in the supplied worktree for coordinator inspection.

## Review and decisions

A fresh independent code reviewer found legacy-UUID replay, ordinary adapter
slot reservation, incomplete preflight identity/plan checks and premature public
handoff state. The corrected protocol queues while the shared claim stays
`execution_intent`, then confirms the exact run/consumer using the original
permit. Regression tests verify these boundaries. A relative-path normalization
finding was also corrected. No final independent acceptance is asserted here.

Rulings made during execution:

- Deliver identities before model execution; never import legacy success as
  stage provenance. Cost if wrong: legacy work still needs manual acceptance.
- Reserve real GitHub pilot, exact-head/base/CI/main/closure for the coordinator,
  as explicitly requested. Cost if wrong: whole-conveyor readiness stays unproven.
- Require the original worker's final CAS for the exact selected consumer/run.
  Cost if wrong: unconfirmed queued identities require owner reconciliation.
- Do not run `task-done` or mark the whole plan task complete under this run's
  authority. Cost if wrong: the coordinator must finish external acceptance.

No deferred minor findings remain. All external acceptance/publication remains
pending. No private installation settings or credentials were inspected, no
authentication/model/provider changed, and no remote publishing, PR creation,
merge, Issue closure, macOS/Linux/WSL execution or diagnostics were performed.


## Coordinator host verification, 2026-11-04

After the actual worker and harness completed with confirmed EOF/cleanup, the trusted Windows host runner executed the complete suite outside the model sandbox: **793 tests, 7 skips, OK**, 1595.516 host seconds. All checked source hashes remained unchanged. The native Superpowers fixture passed on the host; the earlier model-sandbox failure and denied Git staging remain historical evidence.

Independent frozen-source SPEC reviewer `3189e0af-d8ec-4bdd-aa13-0cf02eb4403d` and DEVELOPMENT reviewer `3d06d2a4-352c-4a56-9378-e901d065a04d` returned approve. Their receipts bind the pre-commit source digest, not a committed PR head. Coordinator staging/commit follows verified host completion; fresh committed-head TEST/PR, GitHub acceptance context, Windows CI, real pilot, main acceptance and automatic closure remain separate pending gates. No pipeline history is imported or manufactured from this report.
