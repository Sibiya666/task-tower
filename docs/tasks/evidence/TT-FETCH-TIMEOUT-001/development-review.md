# Independent fetch-budget implementation and recovery-launcher review

Reviewer: /root/fetch_timeout_diagnosis

Verdict: APPROVE scoped product development and focused regression behavior. APPROVE the hash-bound private launcher for a genuine operational recovery cycle. No live postmerge verdict, automatic closure, whole-suite pass, PR approval or night readiness is implied.

Specification review: runtime/fetch-timeout-spec-review.md, raw SHA256 1bffa2f4cf29c7ac1c41177977cdc174041949343ddc008d620c8ef7891fac63.

## Exact reviewed bytes

Product root: task-tower-fetch-timeout

| File | Raw SHA256 |
| --- | --- |
| AGENTS.md | 78befd653272d181565a87d16821c4223e9d09fee0e9660e5131e766a3bcf163 |
| README.md | d58cc0d68b6b1858d6a279b1acbde7892146369f4b564acac48aebd3361fdbd8 |
| docs/postmerge-worker.md | f44f6231d4a38c5b0260d0adbc71c3b326102bbc4d029d658250033afab4e662 |
| docs/superpowers/plans/2026-11-03-postmerge-fetch-budget.md | 762e1e554e526a9a4d09adb4ce3a4d7aece98b5e8d7eac5f107ad2d8cd60d806 |
| task_tower/tasks.py | f08ef728e6a19a22b9a43dbcdd94d5c35c56f27334ab7245960a703088271a65 |
| task_tower/postmerge_worker.py | cb47197c66737129854350a1b1c2a115b3c0c135695f0172fd792df6d8db9ced |
| tests/test_postmerge_fetch_budget.py | ef3d82ffb2e5d1f617ccc9ecd5cb69f2626ec0235856d8502258f67115b5ad53 |

Private launcher runtime/postmerge-fetch-recovery.py raw SHA256: 03106a5722ad00d909ee1dc914518ee7f0bccdfd4d406afad6642a0ce336d6d4.

Independent test script runtime/fetch-timeout-launcher-independent-tests.py raw SHA256: a3506c322b189bd732b01be03901392734d0cc118070fb209e4bc84886c9e68d.

## Product assessment

Inspected the complete tracked diff and added plan/test. The only product behavior changes are a keyword-only tasks._git timeout argument retaining default10, and timeout60 at Worker's exact fetch origin main call. Argument-array execution, check=True, exception conversion, origin match, fresh-fetch ordering, source, journal, independent reviewer, stage evidence and publisher remain unchanged. Documentation accurately describes the separate network budget and fail-closed behavior.

Independently ran the four product regression tests:4 tests in0.002s, OK. They verify unchanged local10s, exact fetch60s, check=True, timeout/nonzero failure before source/review, and invalid-origin rejection before fetch. The existing worker regression log also reports11 tests in16.210s OK; that log was inspected, not represented as an independently rerun result. The complete product suite is coordinator-owned and was still pending at this review.

## Launcher assessment and independent tests

The launcher verifies the complete42 Python-module set and raw bytes against a real local git archive of exact immutable main4875381be68282a7ad77ab7b1c5a3898cbc09304 before importing any task_tower component. It imports those actual pinned components and derives ReceiptWorker with only _refresh overridden. Its refresh retains original origin matching and real bounded argument-array fetch with check=True. The original postmerge_worker.main constructs the genuine GitHubSource, native ReviewRunner, journal and GitHubPublisher. No synthetic CI bundle, verdict, publication or Issue-close call is introduced.

Independently ran six tests of the final hash-bound launcher:6 tests in0.258s, OK. Verified exact successful fetch argv/options; foreign/lookalike/query origin rejection before fetch; timeout/nonzero/OSError abort before source/review; changed module bytes rejection; missing-module set rejection; and delegation to the original main with only the Worker's _refresh override. Tests mock effects and do not run a live reviewer/publisher or change live journal state.

## Review findings and disposition

An earlier launcher pinned only tasks.py/postmerge_worker.py despite claiming unchanged source/review/publication components. The final version pins every Python module before import, addressing the finding.

The first broadened launcher (raw d5a58897caba9c570cf66d928db626ccfc70636829e8ed409026d06ba639f22f) failed immediately with Immutable release source mismatch. Independent inspection proved all42 deployed modules were raw-byte identical to the exact Git archive, but that earlier check normalized only deployed CRLF to LF. The final launcher compares raw archive to raw deployment and passes. This failure occurred during review before live recovery; no source mutation or false success was accepted.

No blocking finding remains in the final reviewed product/launcher bytes. Operational release remains conditional on the coordinator's idle-worker/journal-lock stop, single-writer execution, preserved logs/history and subsequent real exact-main independent acceptance plus automatic Issue16/Project closure verification. The60s subprocess timeout is not a hard process-tree cleanup or unattended-readiness guarantee. Product merge still requires the pending whole-suite/CI and independent exact-head/base PR acceptance after the prior main barrier clears.
