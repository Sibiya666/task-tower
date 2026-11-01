# Whole-Issue development acceptance — Issue #15

Independent reviewer: executor_whole_development. Date: 2026-11-01.

Verdict: **ACCEPTED** for the actual working-tree implementation and documentation bound below. No blocking findings. This is whole-Issue development review, not full-suite test acceptance, PR acceptance, postmerge acceptance, or Issue closure.

Baseline: `cd0927810683edfbc93caf6b6d4db67338aba6f8`. Branch HEAD at inspection: `3ca516476349f38fab1536cb2136de330900da70`. Main/capture integration was resolved in the actual files but not yet committed; README remained unmerged in the index. This verdict binds the file manifest, not that historical HEAD alone. A changed bound file invalidates this snapshot. A later exact-head/base PR review remains mandatory.

Reviewed the complete executor delta against baseline, accepted design and Tasks 1–5 plan, earlier independent stage evidence, production profiles/queue/CLI/worker/harness/process lifecycle, integration and fault tests, and actual shared capability documentation. Read the existing authenticated dispatcher source and dependency verification paths, private-path guards and Windows containment implementation. Authentication repair already belongs to baseline; this diff does not weaken dependency proof.

Authority remains installation owned: exact connected repository/runner/checkout, allowlisted Issue/task/profile, immutable profile fingerprint, approved source reference and pinned instructions. Identity-only adapter input cannot add executable arguments or private authority. Work revalidates current Issue/dependencies, unchanged task data and policy before external effects. Each attempt isolates committed source in a new worktree, records durable intents, strips both GitHub token keys from child environments and validates run/attempt/source-bound strict output. Validated execution_completed does not grant publication, acceptance, merge or closure authority.

Queue admission/lookup is durable and idempotent; collision and foreign/corrupt schema paths fail closed. BEGIN IMMEDIATE serializes local claims/retries and recovery. Unknown ownership consumes capacity, positive local death only fences rather than requeues, and retry archives evidence atomically while requiring proved prelaunch failure and bounded unchanged policy. Cancellation does not transfer ownership. Process capture bounds stored prefixes while reporting observed digests/counts and unknown tails; uncertain cleanup prevents completion. Existing default process API remains routed through its original implementation.

Independent execution: bundled Python 3.12.14 on Windows, `-m unittest tests.test_executor_profiles tests.test_executor_adapter tests.test_executor_queue tests.test_executor_processes tests.test_executor_harness tests.test_executor_worker tests.test_executor_integration -q`: **81 tests, OK (skipped=2), 28.349 seconds**. Initial `python` launch resolved the inaccessible WindowsApps alias and did not execute tests; corrected explicit bundled executable produced this result. `git diff --check BASE -- task_tower tests docs/executor.md README.md AGENTS.md docs/dispatcher.md docs/roadmap.md` passed (Git emitted local line-ending/config-access warnings only). Full integrated suite is owned by the separate test stage; this reviewer does not claim its result. Current required CI remains Python 3.11 on Ubuntu, macOS and Windows.

Reviewed the sanitized installed Codex scratch smoke report as separate supplied evidence: recorded real version/flags, bounded streams, source/result identities and hashes; no generic capability upgrade is inferred. This reviewer did not rerun that installed smoke or independently inspect its private raw artifacts. Fixture transport tests exercise production selection, and the documented scratch run does not prove live Issue authorization, events, resume, automatic stages, persistent refill, distributed ownership or unattended readiness. Worktrees and trusted custom processes retain the documented OS-access limitations; static path validation is not hostile concurrent-filesystem containment.

Canonical binding uses UTF-8 decoded text normalized CRLF/CR to LF; each value below is SHA-256 of those encoded bytes. Manifest digest is SHA-256 of sorted-key compact JSON with ensure_ascii=True. Mutable task cards and all evidence files (including this report) are excluded to avoid self-reference. The six baseline dependency/CI files are included explicitly as inspected context.

Manifest SHA-256: `cff4a0abe5045889f2c4960f8f8181c56903c423bad516e6f173aba01c0e3d63`.

| File | Canonical SHA-256 |
| --- | --- |
| `.github/workflows/cli.yml` | `793c93fe5376cb227d066e17e821ac57d4137768bca64d25ae3b338c965f15c8` |
| `AGENTS.md` | `e88136b8e5b99bfe2c22671c41703e99b55b237d14fadddca2d86d9dd8bcaa35` |
| `README.md` | `89b68f67eeb1cdc837f95d96b029560949fd19bae4ec33192d5ef8f850721d4e` |
| `docs/dispatcher.md` | `40b6ab1e8486a54decc9a8861366af5e7f4d164f9e658d259258558294a671e5` |
| `docs/executor.md` | `fe00349e97b5efb1472eb73c92f8f06251191c847477558762ff9237364d0b6a` |
| `docs/roadmap.md` | `d4757d59be4bed75ba7ef5bda57e4319c0ed4f6855a8173c9d22fa43f1563483` |
| `docs/superpowers/plans/2026-11-01-noninteractive-executor.md` | `58f07c73799d58b4b750ba5c0860aab396287cbcea2717c8bc2bc811a322ecf4` |
| `docs/superpowers/specs/2026-11-01-noninteractive-executor-design.md` | `164ecd8a3c9ec73fab45cf30d4e7ae240eca12cb6d05104d7907f67ab53d4440` |
| `task_tower/__main__.py` | `4535d6724f2e6c24287d2ae1b04a4d08269bc7eacdc689a078504e5a93e418e2` |
| `task_tower/dispatch_selection.py` | `1bdf8204ec789a32c89dd6a5b4345fb94b590dfd2c9df8b8ee9b3ead9ce77088` |
| `task_tower/dispatcher.py` | `b070801cf3085362b730b0adc8028ea91b2d56951be9398037ba3e017d9790e4` |
| `task_tower/executor.py` | `f73c7de951a4a4d47851f501aebe76fc3a83fb94bf0575be5e59feb91cbe1969` |
| `task_tower/executor_harness.py` | `321fae0c390f71cf1a997d0d8cc9e01d7c142220acb18da7779039ac8dce6fc7` |
| `task_tower/executor_profiles.py` | `b80944cceefcb359f4be6597b1780227cb7525da08e2d8c626f6b9b8f4a5d901` |
| `task_tower/executor_queue.py` | `96a9b2802b8d7b1dccfe2277434173bf33d567cd3384c8d02de32f9063044553` |
| `task_tower/executor_worker.py` | `468f1cd11f441c2ac7b614a7f953d1824979850582ed014386f8dfd5d2a0ef33` |
| `task_tower/processes.py` | `881ab6d9cc7cd72bc081dddfe44059a3733ebe6af09728e98d0eea33b2e8b14a` |
| `task_tower/project_connections.py` | `60a300b4275910cf0eee38dfade879d6a9596a36bdd3001928cd8e0d5f55c250` |
| `task_tower/project_worker.py` | `9cb0002ccf5959220b8a7c20b8f656e3f4983319ff0e4805408d44be6fe0b2cc` |
| `task_tower/windows_job.py` | `52f93e53d123bba128714adcf5c1c0836839f4a5f404ecf57d99bbcc8c0c0239` |
| `tests/test_executor_adapter.py` | `b28cbf67831ab43e1d5d3b6601d3e5a8c3480a61dee2f43e802ae8cf5953f528` |
| `tests/test_executor_harness.py` | `47b3f48b4091b4ab05b5b24e47699ee6cbac9a2a7099690227b26e98c4e2bd4a` |
| `tests/test_executor_integration.py` | `e139f77c96ee69186de6eeaa550895044ba833826bc8d7bc76dcfa4e48b511c8` |
| `tests/test_executor_processes.py` | `433bf32aab614d87e0c0caaa52e558a075d7a6ae26c578ed32acfc94b7ef282a` |
| `tests/test_executor_profiles.py` | `26aae2458732e868ffa4290c8d47ef9dec4b3f9389412a58c3bd1131f2ccc8ec` |
| `tests/test_executor_queue.py` | `530ea4b6bcd26b3c67d8c6750c9b4567b1938b9279296ef4ff2d0b9fd75a26a5` |
| `tests/test_executor_worker.py` | `1b2d46bb6b90098baf626245a60e2248b524e4499e197a0dc331d10cc1cb2574` |

Coordinator subsequently committed the resolved integration as `d8b3ea7e597bcb06eb951a442ae629773808c44e`, reporting no bound-byte changes. Historical HEAD above records inspection start; the canonical manifest remains the acceptance binding. Separate test-stage reported full-suite evidence is not substituted for this reviewer's own 81-test run.

## Main #39 and executable-fixture portability supplement — ACCEPTED

Independent reviewer executor_whole_development, 2026-11-01. Current main baseline `f7ce385b89cdddda089985404ce11fffc36a0797`; branch inspection HEAD `3c790eefea9abf1bc20ed94e710f5273e3333f07` with main integration staged and fixture corrections on disk. This refresh accepts those actual bytes, not an uncommitted/index identity or future PR head. Prior evidence remains historical.

Inspected the exact three-expression fixture diff: resolve the test-owned Python executable to its canonical target when building trusted helper profiles (one integration fixture and two worker fixtures). Reversing only these substitutions reproduces both prior accepted canonical file hashes exactly. No production guard, authority policy, assertion, helper protocol or dependency verification changed. Production `_path` still checks each raw path/ancestor through safe_config_path before normalization; profiles with a raw symlink/junction remain rejected. Resolving the fixture's own interpreter accommodates POSIX runtime symlinks without weakening production alias rejection. This supplement explicitly supersedes the old Task 4 worker-test and Task 5 integration-test hash bindings; their unchanged production/source bindings remain applicable.

Read current development-process and session-capture recovery text. The new standalone task-marker/mapping check strengthens merge identity and exact-head/base evidence. Recovery preserves the original unbound event and same open Issue, requires an independently reviewed correctly marked follow-up with prior baseline verification, serializes unrelated merges, and still requires genuine exact-main CI, independent postmerge publication and automatic closure. It does not authorize forged receipts, journal reset or manual closure. It is compatible with the executor spec's separation of execution_completed from integration/closure. Spec and plan bytes remain unchanged; the separate specification supplement binds the new process policy. Session-capture documentation itself belongs to the already reviewed main baseline.

Independent bundled Python 3.12.14 Windows rerun: `-m unittest tests.test_executor_worker tests.test_executor_integration tests.test_executor_profiles -q`: **44 tests OK (skipped=1), 22.176 seconds**. No POSIX or full-suite result is claimed by this review; current all-three-OS CI and independent full-suite test/PR/main gates remain required. No blocking development finding.

Canonical method is unchanged (UTF-8/LF; compact sorted JSON manifest SHA-256). The 27 previous inputs are refreshed and current development-process is added, for 28 bound files. Mutable cards/evidence remain excluded. Manifest SHA-256: `4794fd80aadf471fb7a9ed684971514b0c603916eca869760d09c2bba42ff0f0`.

| File | Canonical SHA-256 |
| --- | --- |
| `.github/workflows/cli.yml` | `793c93fe5376cb227d066e17e821ac57d4137768bca64d25ae3b338c965f15c8` |
| `AGENTS.md` | `e88136b8e5b99bfe2c22671c41703e99b55b237d14fadddca2d86d9dd8bcaa35` |
| `README.md` | `89b68f67eeb1cdc837f95d96b029560949fd19bae4ec33192d5ef8f850721d4e` |
| `docs/development-process.md` | `c0a5cdb73ceb45b855064e408e9f2ecb55ff520b76cd83b079cd05a3a54a09c9` |
| `docs/dispatcher.md` | `40b6ab1e8486a54decc9a8861366af5e7f4d164f9e658d259258558294a671e5` |
| `docs/executor.md` | `fe00349e97b5efb1472eb73c92f8f06251191c847477558762ff9237364d0b6a` |
| `docs/roadmap.md` | `d4757d59be4bed75ba7ef5bda57e4319c0ed4f6855a8173c9d22fa43f1563483` |
| `docs/superpowers/plans/2026-11-01-noninteractive-executor.md` | `58f07c73799d58b4b750ba5c0860aab396287cbcea2717c8bc2bc811a322ecf4` |
| `docs/superpowers/specs/2026-11-01-noninteractive-executor-design.md` | `164ecd8a3c9ec73fab45cf30d4e7ae240eca12cb6d05104d7907f67ab53d4440` |
| `task_tower/__main__.py` | `4535d6724f2e6c24287d2ae1b04a4d08269bc7eacdc689a078504e5a93e418e2` |
| `task_tower/dispatch_selection.py` | `1bdf8204ec789a32c89dd6a5b4345fb94b590dfd2c9df8b8ee9b3ead9ce77088` |
| `task_tower/dispatcher.py` | `b070801cf3085362b730b0adc8028ea91b2d56951be9398037ba3e017d9790e4` |
| `task_tower/executor.py` | `f73c7de951a4a4d47851f501aebe76fc3a83fb94bf0575be5e59feb91cbe1969` |
| `task_tower/executor_harness.py` | `321fae0c390f71cf1a997d0d8cc9e01d7c142220acb18da7779039ac8dce6fc7` |
| `task_tower/executor_profiles.py` | `b80944cceefcb359f4be6597b1780227cb7525da08e2d8c626f6b9b8f4a5d901` |
| `task_tower/executor_queue.py` | `96a9b2802b8d7b1dccfe2277434173bf33d567cd3384c8d02de32f9063044553` |
| `task_tower/executor_worker.py` | `468f1cd11f441c2ac7b614a7f953d1824979850582ed014386f8dfd5d2a0ef33` |
| `task_tower/processes.py` | `881ab6d9cc7cd72bc081dddfe44059a3733ebe6af09728e98d0eea33b2e8b14a` |
| `task_tower/project_connections.py` | `60a300b4275910cf0eee38dfade879d6a9596a36bdd3001928cd8e0d5f55c250` |
| `task_tower/project_worker.py` | `9cb0002ccf5959220b8a7c20b8f656e3f4983319ff0e4805408d44be6fe0b2cc` |
| `task_tower/windows_job.py` | `52f93e53d123bba128714adcf5c1c0836839f4a5f404ecf57d99bbcc8c0c0239` |
| `tests/test_executor_adapter.py` | `b28cbf67831ab43e1d5d3b6601d3e5a8c3480a61dee2f43e802ae8cf5953f528` |
| `tests/test_executor_harness.py` | `47b3f48b4091b4ab05b5b24e47699ee6cbac9a2a7099690227b26e98c4e2bd4a` |
| `tests/test_executor_integration.py` | `01964a00cd94172a95a8960dbaf369de89ad6cff36f24b8c1d30ced1bb790740` |
| `tests/test_executor_processes.py` | `433bf32aab614d87e0c0caaa52e558a075d7a6ae26c578ed32acfc94b7ef282a` |
| `tests/test_executor_profiles.py` | `26aae2458732e868ffa4290c8d47ef9dec4b3f9389412a58c3bd1131f2ccc8ec` |
| `tests/test_executor_queue.py` | `530ea4b6bcd26b3c67d8c6750c9b4567b1938b9279296ef4ff2d0b9fd75a26a5` |
| `tests/test_executor_worker.py` | `9f9ab044a602084aec74bd93b072e285d952bbd2eff619fab15893e9d8b9ad2a` |

## Python 3.11 junction guard and macOS fixture supplement — ACCEPTED

Independent reviewer executor_whole_development, 2026-11-01, distinct from implementation/fixer instances. Inspection HEAD `2022439e45e47816218a606ded73564f6c1e2627`, base main `f7ce385b89cdddda089985404ce11fffc36a0797`; corrections are actual uncommitted working-tree bytes. No blocking finding. Historical acceptance remains preserved but changed file bindings are superseded below. Fresh exact-head/base PR acceptance and current CI remain separate gates.

Inspected the actual four-file delta. `_capture_files` now lstat-checks the supplied directory and every ancestor, rejects the Windows reparse bit (portable constant/fallback 0x400), retains symlink rejection and raises fixed unsafe_capture_directory ValueError on lstat OSError. This runs before log creation or executable lookup and does not require Python 3.12 Path.is_junction. Existing files remain exclusively created. Both the target junction and an aliased ancestor are covered by a real Windows junction regression which temporarily removes Path.is_junction and restores it in finally. No process-launch, cleanup, output, authority or dependency behavior changed. Static path checks retain the existing limitation against hostile concurrent filesystem mutation.

The remaining changes canonicalize test-owned temporary roots before supplying legitimate fixture paths in process/harness/one worker test. Assertions and malformed-output cases remain intact; alias tests still explicitly create unsafe aliases and pass those raw aliases to production. This accommodates macOS temporary-root aliases without resolving untrusted production inputs. Source/spec/plan and installation authority remain unchanged apart from the corrected capture guard.

Independent bundled Python 3.12.14 Windows run with PYTHONPATH=tests: `-m unittest tests.test_executor_processes tests.test_processes tests.test_worker_cli tests.test_project_worker tests.test_postmerge_worker tests.test_executor_worker tests.test_executor_harness -q`: **76 tests OK (skipped=1), 33.201 seconds**. The real junction regression ran. Independent missing-directory, regular-file-as-directory and injected lstat PermissionError probes returned unsafe_capture_directory, did not call executable lookup and created no logs. Focused diff-check passed. This reviewer did not execute real Python 3.11 or macOS; mandatory current all-three-OS Python 3.11 CI remains the portability gate. Full-suite acceptance is separate. No downloaded CI failure log inspection is claimed.

This whole-development supplement refreshes the four changed bindings, explicitly including Task 4 worker/harness test bindings. Other 24 manifest files remain unchanged from the prior 28-file acceptance; no spec-policy reacceptance is needed. Canonical method remains UTF-8/LF with SHA-256 of compact sorted-key ensure_ascii JSON. Mutable cards and evidence remain excluded. Current 28-file manifest SHA-256: `48fadafcb7c70799716affb9698a92420fe8039fe478792536b14ed17b6a52f8`.

| File | Canonical SHA-256 |
| --- | --- |
| `.github/workflows/cli.yml` | `793c93fe5376cb227d066e17e821ac57d4137768bca64d25ae3b338c965f15c8` |
| `AGENTS.md` | `e88136b8e5b99bfe2c22671c41703e99b55b237d14fadddca2d86d9dd8bcaa35` |
| `README.md` | `89b68f67eeb1cdc837f95d96b029560949fd19bae4ec33192d5ef8f850721d4e` |
| `docs/development-process.md` | `c0a5cdb73ceb45b855064e408e9f2ecb55ff520b76cd83b079cd05a3a54a09c9` |
| `docs/dispatcher.md` | `40b6ab1e8486a54decc9a8861366af5e7f4d164f9e658d259258558294a671e5` |
| `docs/executor.md` | `fe00349e97b5efb1472eb73c92f8f06251191c847477558762ff9237364d0b6a` |
| `docs/roadmap.md` | `d4757d59be4bed75ba7ef5bda57e4319c0ed4f6855a8173c9d22fa43f1563483` |
| `docs/superpowers/plans/2026-11-01-noninteractive-executor.md` | `58f07c73799d58b4b750ba5c0860aab396287cbcea2717c8bc2bc811a322ecf4` |
| `docs/superpowers/specs/2026-11-01-noninteractive-executor-design.md` | `164ecd8a3c9ec73fab45cf30d4e7ae240eca12cb6d05104d7907f67ab53d4440` |
| `task_tower/__main__.py` | `4535d6724f2e6c24287d2ae1b04a4d08269bc7eacdc689a078504e5a93e418e2` |
| `task_tower/dispatch_selection.py` | `1bdf8204ec789a32c89dd6a5b4345fb94b590dfd2c9df8b8ee9b3ead9ce77088` |
| `task_tower/dispatcher.py` | `b070801cf3085362b730b0adc8028ea91b2d56951be9398037ba3e017d9790e4` |
| `task_tower/executor.py` | `f73c7de951a4a4d47851f501aebe76fc3a83fb94bf0575be5e59feb91cbe1969` |
| `task_tower/executor_harness.py` | `321fae0c390f71cf1a997d0d8cc9e01d7c142220acb18da7779039ac8dce6fc7` |
| `task_tower/executor_profiles.py` | `b80944cceefcb359f4be6597b1780227cb7525da08e2d8c626f6b9b8f4a5d901` |
| `task_tower/executor_queue.py` | `96a9b2802b8d7b1dccfe2277434173bf33d567cd3384c8d02de32f9063044553` |
| `task_tower/executor_worker.py` | `468f1cd11f441c2ac7b614a7f953d1824979850582ed014386f8dfd5d2a0ef33` |
| `task_tower/processes.py` | `50d2feddcfad3530d3ab63c94bc514b78f082e330de99543e857259cc951c729` |
| `task_tower/project_connections.py` | `60a300b4275910cf0eee38dfade879d6a9596a36bdd3001928cd8e0d5f55c250` |
| `task_tower/project_worker.py` | `9cb0002ccf5959220b8a7c20b8f656e3f4983319ff0e4805408d44be6fe0b2cc` |
| `task_tower/windows_job.py` | `52f93e53d123bba128714adcf5c1c0836839f4a5f404ecf57d99bbcc8c0c0239` |
| `tests/test_executor_adapter.py` | `b28cbf67831ab43e1d5d3b6601d3e5a8c3480a61dee2f43e802ae8cf5953f528` |
| `tests/test_executor_harness.py` | `bc1d67df95c74f11d56059f50aedd5aff2455a8ff244fab5c148c31fa3ad84a0` |
| `tests/test_executor_integration.py` | `01964a00cd94172a95a8960dbaf369de89ad6cff36f24b8c1d30ced1bb790740` |
| `tests/test_executor_processes.py` | `39fa03f0a0b195871e431f3cbfe269efc70b2b500314ddc7670c7dec57020ee3` |
| `tests/test_executor_profiles.py` | `26aae2458732e868ffa4290c8d47ef9dec4b3f9389412a58c3bd1131f2ccc8ec` |
| `tests/test_executor_queue.py` | `530ea4b6bcd26b3c67d8c6750c9b4567b1938b9279296ef4ff2d0b9fd75a26a5` |
| `tests/test_executor_worker.py` | `e03851eed4f0ccf18695d9b209e65098343f72a8fbf7fea21ba3247f4da649f9` |
