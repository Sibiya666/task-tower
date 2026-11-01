# Task 2 independent review - TT-EXECUTOR-001 / Issue #15

Verdict: **REJECTED** (2026-11-01), bound to the five canonical source hashes below. Reviewer executor_queue_review is distinct from the implementer. No production edits, commits, remote operations or delegated children were made. This is a Task 2 verdict, not whole-Issue, PR or postmerge acceptance.

Reviewed repository AGENTS, accepted updated executor spec/plan, actual queue/adapter implementations, tests and executor CLI route. Task 4 worker is intentionally unavailable in this snapshot and is not a Task 2 rejection reason.

## Blocking finding

P1 - `ExecutionQueue.record` silently overwrites persisted provenance through `saved.update(evidence)`. A valid owner can first record, while claimed, `source_sha='a'*40`, `worktree_hash='b'*64`, `launch_intent=True`, then perform another same-state record with `source_sha='c'*40`, `worktree_hash='d'*64`, `launch_intent=False`. Both transactions succeed; status exposes only the replacement SHA/hash and false intent. Independently reproduced against these actual files using a temporary queue. The queue loses evidence of the original intent/source and cannot distinguish mutation from the legitimate Task 4 addition of new neutral evidence keys.

Require existing evidence keys to remain equal (idempotent repeats permitted) while allowing new validated neutral keys. Reject any conflicting value atomically without changing state or other evidence. Add a regression covering source/worktree/launch intent replacement, allowed additive writes, repeated identical writes and transaction rollback. This is the only blocking finding identified in this review.

## Verification and conclusions

Actual bundled Python `C:/Users/sibiya666/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe -m unittest tests.test_executor_queue tests.test_executor_adapter -v`: 15 tests PASS (0.941 seconds). Full suite deliberately not run while Task 4 modules remain in motion.

Tests and inspection establish strict six-key UUID/task admission; commit precedes returning acknowledgement; repeated deliveries retain a receipt while identity/profile collisions fail closed. Adapter lookup rechecks full identity/profile and returns unknown on policy mismatch. CLI status/cancel require current connections and no profile config, preserving cancellation after profile revocation. Missing queues are not created by lookup. Private checkout exclusions, hardlink aliases/input collisions, foreign schema/corrupt ownership and WAL rejection are fail closed; WAL lookup test compares all bytes before/after. WAL queues are unsupported, rather than opened with side effects.

Claims use BEGIN IMMEDIATE, enforce maximum two active claimed/running/unknown entries and do not reclaim uncertainty. Independent real-process tests prove one winner for competing claims, live sibling recovery preservation, and dead registered-owner recovery to unknown. Unregistered claims have no owner PID and are not automatically fenced; PID reuse/liveness uncertainty remains conservative. Owner/state transitions reject foreign owners and transitions from unknown. Same-state intent recording is correctly available, but its existing-key immutability is the blocking defect above. Neutral evidence validation excludes arbitrary prose, paths and token values by shape. Recovery does not authorize takeover or rerun.

## Canonical source manifest

SHA-256 over UTF-8 text normalized to LF. Evidence excluded to avoid self-reference. Any changed bound input requires a new review supplement; preserve this rejected-stage history.

| File | Canonical SHA-256 |
| --- | --- |
| `task_tower/executor_queue.py` | `c535ad51f55067e9252fd2d00c089144e35625304205f0b71fdf536417bc4c91` |
| `task_tower/executor.py` | `000a3e8318b2294be260d9d3dbd4fea04cb42476fc6025f2bdd705cb11527a66` |
| `tests/test_executor_queue.py` | `97aa1d615caa01e04716e679bcf91d98e8a5663cd6544ca94e414a2a00a6db6d` |
| `tests/test_executor_adapter.py` | `f39525c7a0c72b2ac7b43943480b8515f0be640cb05fc32ee722fcfbaa255d78` |
| `task_tower/__main__.py` | `861f4a3fc7b22e7425cdb2114efc334358fb3abc84605fc52b17c2f8d1582e30` |

## Current R1 rereview supplement - ACCEPTED

Historical rejection above is preserved. Current Task 2 verdict: **ACCEPTED**, bound only to the five canonical source hashes below. No whole-Issue, PR, real Codex execution or postmerge acceptance is implied.

Independently inspected the queue/test delta and reran actual bundled Python `-m unittest tests.test_executor_queue tests.test_executor_adapter -v`: 16 tests PASS in 0.883 seconds. The new regression rejects conflicting source/worktree/launch evidence without persisting attempted state or additive keys, while permitting identical and additive writes.

Independently reran the original multi-key replacement counterexample, plus boolean/integer equal-value type changes (`True` to `1` and `1` to `True`). Every conflict raised ValueError and left the full status unchanged. Identical evidence and new neutral keys succeeded in claimed/running same-state writes and a valid claimed-to-running transition. Existing-key type/value comparison now occurs before mutation under the existing transaction; the P1 finding is resolved. No remaining blocking finding within Task 2 scope. Previous scope limitations continue to apply. No production changes or remote operations were made by the reviewer.

| File | Current canonical SHA-256 |
| --- | --- |
| `task_tower/executor_queue.py` | `c17669ecae830591c68d83c9de94762f8ccb6c84e20193f19c927e6fe9b6f73a` |
| `task_tower/executor.py` | `000a3e8318b2294be260d9d3dbd4fea04cb42476fc6025f2bdd705cb11527a66` |
| `tests/test_executor_queue.py` | `a0caae77227931e76ef9f21650d4467d0418998d2c66a018faae4d18181aad6f` |
| `tests/test_executor_adapter.py` | `f39525c7a0c72b2ac7b43943480b8515f0be640cb05fc32ee722fcfbaa255d78` |
| `task_tower/__main__.py` | `861f4a3fc7b22e7425cdb2114efc334358fb3abc84605fc52b17c2f8d1582e30` |

## Current Task 4 retry extension review - ACCEPTED

Current extension verdict: **ACCEPTED**, limited to the two canonical hashes below. Prior Task 2 rejection and repaired acceptance are preserved. Their executor.py, adapter-test and __main__.py bindings describe the historical Task 2 snapshot; expected Task 4 CLI changes are outside this extension review. No whole-Issue, CLI, PR or postmerge acceptance is implied.

Independently inspected schema V2, history validation, retry_prelaunch/history APIs and queue tests. Retry requires failed state, strict boolean started=False/cleanup_confirmed=True/prelaunch_failure=True proof, no cancellation, unchanged profile fingerprint, strict integer max_attempts 1..10 and attempt below limit. Complete prior neutral ownership/evidence is archived before clearing current fields, atomically under BEGIN IMMEDIATE with a queued-state CAS. Next claim increments the retained ordinal and generates a fresh attempt UUID. Unknown/started/unproved attempts cannot retry. Evidence immutability remains enforced. Caller must supply currently revalidated installation policy; the queue does not independently load authority.

Actual bundled Python `-m unittest tests.test_executor_queue tests.test_executor_adapter -q`: 23 tests PASS in 2.570 seconds, including real concurrent retry single winner, rollback before commit, false-versus-zero proof, policy/state/cancellation gates and nine archived attempts before the tenth-attempt cap. Old V1 schema is rejected without migration.

Independent temporary-queue probes mutated/cleared returned history objects; stored history remained intact. Repeated history reads preserved every directory filename and byte. A foreign extra table caused history and retry to reject without changing directory bytes. Initial probe assertions passed but its reviewer-owned SQLite connection was not explicitly closed, causing temporary-directory cleanup failure; corrected explicit-closing rerun passed including cleanup. Inspection confirms archive/CAS share rollback. No blocking finding. Full moving Issue suite was not run. No production edits, remote operations, commits or delegated children were made.

| File | Current extension canonical SHA-256 |
| --- | --- |
| `task_tower/executor_queue.py` | `96a9b2802b8d7b1dccfe2277434173bf33d567cd3384c8d02de32f9063044553` |
| `tests/test_executor_queue.py` | `ab92ff1040b2a28ef15662c66aeae2ef44e65062c3efe3e35b8fb4b387c96e59` |


## Temporary-path portability supplement - ACCEPTED

Independent reviewer executor_fixture_review accepts only the two fixture changes bound below (2026-11-01). Historical verdicts remain preserved. Replacing `Path(self.tmp.name).resolve()` with `Path(self.tmp.name)` in memory reproduces the prior accepted canonical hashes exactly: queue `ab92ff1040b2a28ef15662c66aeae2ef44e65062c3efe3e35b8fb4b387c96e59`, adapter `f39525c7a0c72b2ac7b43943480b8515f0be640cb05fc32ee722fcfbaa255d78`. Thus the complete two-file delta is eight queue fixture/path references and one adapter fixture root resolution; there are no changed assertions or other test changes.

Inspected actual constructors and safe_config_path: ExecutionQueue still validates the supplied path and its ancestors before opening, and the production guard still rejects symlinks/reparse points before resolution. Fixture canonicalization accommodates a platform temporary directory alias (including macOS /var to /private/var) before supplying test-owned paths; it does not weaken production validation or its policy. No production changes were made by this reviewer.

Independent bundled Python `-m unittest tests.test_executor_queue tests.test_executor_adapter -q`: 23 tests PASS in 2.428 seconds on this Windows host. No blocking finding in this narrow supplement. All-three-OS CI, whole-Issue, PR and postmerge acceptance remain separate requirements and are not established here. No commits or remote operations were made.

Canonical SHA-256 over UTF-8 text normalized to LF:

| File | Current canonical SHA-256 |
| --- | --- |
| `tests/test_executor_queue.py` | `530ea4b6bcd26b3c67d8c6750c9b4567b1938b9279296ef4ff2d0b9fd75a26a5` |
| `tests/test_executor_adapter.py` | `b28cbf67831ab43e1d5d3b6601d3e5a8c3480a61dee2f43e802ae8cf5953f528` |
