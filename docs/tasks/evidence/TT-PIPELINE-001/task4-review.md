# Task 4 independent controller review

Verdict: **accepted within Task 4 scope**, 2026-11-02. Independent reviewer: `/root/pipeline_worker_review`, distinct from the implementer. No blocking findings remain in the two Task 4 files. This is not whole-Issue, publication, watch, CI, PR-head/base or main acceptance.

Reviewed the actual controller and tests against repository AGENTS, the accepted stage-pipeline specification and implementation plan, and all thirteen implementation-ledger rulings. Initial review HEAD was `ff7f39c889f891d2747de6fb56f418c171ceab20`; the final dependency-only guard commit is `f5a9e5bf3c0c59a9bd8299e289f6dc3f2b6e5c36`. Task 4 files were uncommitted new files throughout this review and remained unchanged after the corrected freeze below.

## Exact accepted bindings

Canonical hashes use strict UTF-8 with CRLF/bare CR converted to LF, preserving all other content. Both raw and canonical hashes were computed independently.

| File | Raw SHA256 | Canonical SHA256 |
| --- | --- | --- |
| task_tower/pipeline_worker.py | 5b405cea80d5a54a352649de2b94d337e756c7fbce3a61407f268de0a92e7842 | e1dbbb0e20e85686009ef74f7d9ed1bf35067f6e97f1eb0f93b6cbca2ab6d9bd |
| tests/test_pipeline_worker.py | 82c23d1392b73cadbdfec09e687e09e8603bac049719b713ae9370c21ccdf3e2 | b29ce410a3c83fd2ce5829dcab3a6c0f3e422dc5a13cf569a081fe7c92fc9a43 |

Current dependency bindings: pipeline_inputs.py `ad11e773f7564204edc58e0a080d9f667d657afa48997e07ef343e1214f8bc16`; pipeline_journal.py `58bf6caf92ec9ba39d61f6e92914c0bfed5f3ea803c36ad8ce21201a8e89045f`; tests/test_pipeline_journal.py `c108186861c59874f49d2bb6267bf0b045c64b7cb8395cd2cf650976f7bf4013`. These raw hashes equal canonical hashes. Task 2 R3 has its own fresh independent acceptance in task2-review.md.

Specification hash: `8de84fe1a6ea7e22f104a2b5812e86bedea97c9363cf0971bbbea5eba0fd0f77`; plan: `4f13c9eb4bf4222a1cdebf5c677b7ed932d8415f386ee9623ade02906b916feb`; thirteen-ruling ledger: `e1f5f48a93f4c90914abd6637891852a85060a14f7bca62ea8c1da09d34b41be` (raw and canonical equal).

## Independent verification

Commands used absolute Python `C:/Users/sibiya666/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe`, from this checkout, with actual Git repositories/worktrees and child processes. No product files were edited by this reviewer.

1. `-m unittest tests.test_pipeline_worker -v`: **29 tests, 350.413 seconds, OK**, exit 0 (session 75798). This independently covered the corrected Task 4 files against the previously accepted journal `61b82e11015130b9f443adeee7c38300a941e5b35925295cccc938541a18b43e`.
2. After the three-line R3 journal tightening, independently inspected that entire production diff and its ten-line regression addition. The new guard validates both creation-intent paths with the existing strict host-directory validator and independently rejects null saved identities at initial-ready. It does not change valid controller paths or flow.
3. Current-R3 rebind: `-m unittest tests.test_pipeline_worker.WorkerTests.test_real_git_preparation_binds_exact_identity tests.test_pipeline_worker.WorkerTests.test_six_roles_in_order_with_receipt_bindings tests.test_pipeline_worker.WorkerTests.test_dead_ready_handoff_preserves_deadline_and_counters -v`: **3 tests, 35.403 seconds, OK**, exit 0 (session 34645). Start/end product hashes matched the bindings above. This proves actual initial preparation, all six role processes plus host checks/checkpoints, and positive-dead ready handoff against the current guard. The full 29-test run is explicitly old-dependency proof; it is not represented as a full current-R3 rerun.
4. Additional independent real-child probes, outside the supplied test methods, passed: after a genuinely completed spec reviewer, adding a duplicate verdict key to its actual private result parked `needs_input/environment_unavailable` with no receipt; changing the actual authoritative Issue title immediately after reviewer completion parked `needs_input/policy_revoked` with no receipt. Both retained positive cleanup evidence. Transport fixtures remained at the source seam; neither probe replaced continuation authorization with true.

The coordinator separately reports the author Task 1–4 combined run: 134 tests, 482.193 seconds, OK, one skip, before the R3 guard; Task 2 R3 author and independent guard suites are recorded in task2-review.md. These are distinct from the independent commands above. Full current integration verification remains a later gate.

## Controller findings

Fresh authority compares actual journal ownership/CAS/manifest/worktree identity, private continuation policy and pins, current authoritative Issue criteria/dependencies/main, deadline and actual product/checkpoint. Actual Issue data reaches the child explicitly labelled untrusted. Verdict persistence reconstructs the binding from the actual stored reviewer attempt, revalidates request/instruction/result bytes, process completion and unchanged source, and rechecks authority/product/authoritative CI immediately before saving. Model completion, editable cards and publisher callback returns cannot mint journal acceptance.

The deterministic sequence keeps initial preparation, six independent roles, normal checkpoints and the configured host-check batch distinct. Initial preparation ends ready without launching a role. Receipt/history gates retain prior-stage approval, fresh contributor boundaries and generation bindings. Missing publication integration leaves the accepted run ready with fixed environment_unavailable; a callback return alone cannot declare awaiting_pr. Task 5 publication and Task 6 CLI/watch are intentionally outside this acceptance.

Typed rejection preserves immutable history, consumes bounded target rework and invalidates downstream receipts. Development changes to accepted spec/plan return to fresh spec work. Failed test-executor or host-check product mutations use actual linked forensic rework commits and return to fresh development; they do not become successful normal contributors. Unattributable dirt parks safely. Completed checkpoint crash recovery verifies immutable Git blobs and refuses later dirty content without producing another commit.

Ready restart uses positive-death handoff without extending persisted deadlines/counters or replaying completed roles. Live/unknown ownership and unresolved intents remain fenced. Cancellation during an actual running child waits for positive cleanup; unknown cleanup retains the unknown state. Persisted process limits stop before further effects. The corrected live monotonic anchor survives successive step calls through journal-owned per-run clocks. Checks require actual host results and source preservation; current CI evidence cannot turn failed checks or reviewer needs_input into approval.

## Invalidated freeze history and limits

The originally supplied worker `058ba7c7b4bdfdf7a6645226996d63e01250ae61b21eba04c819decaf031cd50` and test `02c5a4971cca824cf492eaf31351fc854b861340d7f546a69c504286ee3533f7` freeze was invalidated during this review for the discovered monotonic-anchor lifetime bug. Historical session 24631 loaded the older worker and finished 29 tests in 353.186 seconds with the monotonic regression failing. It is not passing final proof. The corrected freeze's fresh full suite passed that regression. Earlier historical 23-test results are likewise not final proof.

Builder check: **nothing important left within the Task 4 boundary**. No product edit, commit or push was made by this reviewer. Changing either Task 4 binding or the accepted dependency contracts invalidates this scoped verdict. Whole-implementation/test acceptance, real installed-runtime pilot, publication/watch validation and all serialized GitHub integration gates remain required.
