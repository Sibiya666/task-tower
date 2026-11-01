# Task 1 independent policy and authority review

Verdict: **rejected**. Reviewer: fresh `/root/pipeline_policy_review`, distinct from implementer. Base checkout HEAD `b3f9836025210d05ad1ab1c551e4b5821e26dfc8`. No source changes or commits performed.

Reviewed complete `task_tower/pipeline_policy.py` and `tests/test_pipeline_policy.py`, accepted spec `8de84fe1a6ea7e22f104a2b5812e86bedea97c9363cf0971bbbea5eba0fd0f77`, plan `4f13c9eb4bf4222a1cdebf5c677b7ed932d8415f386ee9623ade02906b916feb` Task 1, current spec-review and implementation-ledger rulings, repository AGENTS, and actual profile, metadata, selection and lifecycle/dependency seams.

Canonical UTF-8/LF source bindings observed:

- policy: `2490774eb59a14deca7a47ee9720f4b2ce0655bcb2a40fad4096549490a5beb9` (assigned binding matches).
- tests: `f926b54a440a0f0898204e896278afc63969827a3b224f6022884bcaece73e49` (assigned frozen binding was `6679899f85ee7d01c5ee048c6a799beaaf66807c9dac2842ee4f1e6379207a7f`; mismatch invalidates acceptance of that pair).

## Blocking findings

1. **P1, pipeline_policy.py:107-110 — active normalized policy can diverge from its authority digest.** `_current` reloads installed bytes and compares the reload digest to the cached `config['policy_sha256']`, but never recomputes the digest of active normalized `tasks` and limits. Independently loaded a valid policy, changed `tasks[0].publish.enabled` from false to true, changed allowed_paths to `['outside/']`, and set max_processes to 1000000. `admission_authorized` still returned admission carrying the unchanged policy digest. These are the policy fields downstream host actions consume. Enforce equality with the fresh canonical normalized policy (or use that fresh policy), including every public task/limit, before admission and continuation; add mutation negatives. Host-owned hooks remain outside JSON/digest.

2. **P2, pipeline_policy.py:16-17,48-50 — Windows path aliases bypass overlap rejection.** A full valid configuration with allowed_paths `['src/','docs/','docs./']` is accepted. Windows normal file APIs treat trailing-dot/space components as aliases, so these are overlapping authority prefixes despite literal comparisons. `_relative` also accepts `docs /`, `docs/file.` and reserved `docs/aux`. Reject platform-ambiguous components consistently before prefix comparison and later product mapping. The cross-platform spec explicitly rejects overlapping aliases.

## Verification and strengths

Executed the plan's focus command with the absolute approved Python runtime: `-m unittest tests.test_pipeline_policy tests.test_executor_profiles tests.test_dispatch_selection -v`: **41 tests, OK, one symlink privilege skip**. All 13 policy tests pass against the real current PipelineJournal, including private owner/delivery bindings and genuine Actions ZIP/hash-backed verified_done dependency proof followed by digest revocation. No dependency predicate was replaced with a true callback.

Independent negative probes confirmed missing/noncallable/false/raising host authority callbacks block; false/None/zero/empty authority results block; ordinary prose comments survive criteria extraction, unknown structurally valid task metadata is stripped as metadata, and final newline change binds criteria. Source inspection confirms duplicate JSON rejection, strict Boolean/integer bounds, exact 13 task keys, allowlist/profile/publisher binding, private installed path/pin checks, unchanged real select_ready for initial admission, real journal owner-bound continuation without forged open metadata, current authoritative main/source comparison, lifecycle history and cancellation guards. Host callback construction and saved dispatcher backend scope remain Task 6 obligations; this review grants no cross-database exclusion or unattended-runtime acceptance.

Additional combined `tests.test_pipeline_policy tests.test_pipeline_journal` run: 36 tests, one failure in Task 2 WIP `HistoryGateTests.test_state_and_neutral_evidence_cannot_forge_stage_completion`, line 128 (`ready` unexpectedly accepted). Reported to coordinator; dependency files were not altered. This does not invalidate the passing Task 1 focused result but blocks claiming the combined journal stage accepted.

This verdict is Task 1 only and grants no PR/main/Issue completion acceptance. Fresh bindings and independent re-review are required after fixes.

## Current R1 independent re-review — accepted

Verdict: **accepted for Task 1**, superseding the initial rejection above. Freshly read the complete revised policy and changed tests against the same accepted Task 1 specification/plan and coordinator rulings. Source checkout HEAD remains `b3f9836025210d05ad1ab1c551e4b5821e26dfc8`; source files are currently untracked work in progress, so the following exact file bindings, not HEAD alone, define this review:

- `task_tower/pipeline_policy.py`: `1b677caee3cd41d947218f080df46ba62ddb0e659d2b50a00cfa8931e1fa7e0f`.
- `tests/test_pipeline_policy.py`: `3aef6be9692727d19f90f8a2e2ebfd8f5b334b4e10b43f108ba309e4f3453b7c`.

Independently computed both raw-byte SHA-256 and canonical CRLF/bare-CR-to-LF SHA-256; they are identical for both R1 files and match the newly assigned frozen values. The historical test binding mismatch is retained above as observed; raw versus canonical hashing of mixed line endings explains why those historical representations were different, and is not claimed to be an unchanged historical binding.

Both blocking findings are resolved. `_current` now compares canonical fingerprints of the entire active public normalized object with freshly loaded installed policy, including nested task mappings, checks, publication, paths, components, limits, profiles and policy digest. Retained executor-config and connection fingerprints detect drift in allowlist and checkout/publisher context; the mandatory host callback still supplies saved connection/executor-config byte authority. Admission requires the complete trusted task row rather than an arbitrary delivery-shaped object sharing identity. Continuation still obtains actual saved PipelineJournal state and host owner, never model-owned ownership evidence. `_relative` rejects trailing dot/space, Windows illegal/control characters and reserved device names including superscript COM/LPT aliases, while preserving valid Unicode paths.

Independent verification: focused `tests.test_pipeline_policy tests.test_executor_profiles tests.test_dispatch_selection`: **45 tests, OK, one symlink privilege skip**. Additional independent probes mutated nested check argv, CI substitution, component list, Boolean role timeout and nested instruction manifest; every admission was blocked. A copied task row with forged publisher was blocked. Trailing-dot/space, COM-superscript/LPT-superscript, wildcard and NUL device paths were rejected; Cyrillic paths remained valid. Existing actual-journal owned continuation, lifecycle/criteria/source/cancellation and genuine Actions ZIP/hash dependency-revocation tests pass in that focused suite. No new blocking Task 1 findings remain.

Test limitation: a subsequent combined policy+journal run encountered **35 tests, three Task 2 WIP errors**, all `ValueError: Receipt checkpoint contribution missing`, in `AttemptTests.test_receipt_requires_host_launched_fresh_reviewer_and_preserves_rejection`, `GenerationTests.test_executor_output_freezes_new_reviewer_generation`, and `StaleReceiptTests.test_valid_stale_receipt_preserved_but_never_effective`. Task 2 files were changing independently during this review. Reported the errors to the coordinator and did not modify dependency files. This Task 1 verdict does not accept Task 2 or claim the combined suite passes.

Host callback construction and saved dispatcher backend/journal overlap remain Task 6 integration obligations. This review supplies no PR/main acceptance, cross-database exclusion claim, or unattended execution claim. Any change to the bound Task 1 files invalidates this R1 verdict and requires re-review. No source modifications or commits were made by this reviewer.
