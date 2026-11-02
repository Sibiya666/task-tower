# Independent Task 2 implementation review

2026-11-02. Reviewer `/root/groups_policy_acceptance`, distinct from implementer. **REJECTED pending P2 partial-source classification correction below.** Pure graph/read-only observation review only; no whole-development/TEST, Issue18 runtime, PR/main/postmerge or Issue closure acceptance.

## Exact binding

Independently observed HEAD `fea86491410a0fecf83022ad8bf7cef3477a41d0`, branch feat/agent-groups. Reviewed both entire new untracked files, accepted Task 2 plan/design, capture.relationship_projection, dispatch_selection.collect_snapshot, GitHubSource.poll/_poll and production project_worker.verified_done/verified_receipt/verified_local_receipt/issue_lifecycle paths. Product raw and canonical hashes are identical:

| File | SHA-256 |
| --- | --- |
| task_tower/group_graph.py | `4e70a84e1f33b9061eae2f44085d5df68bda433a9909734b49cceae56b26abd8` |
| tests/test_group_graph.py | `8ab4768ae5eb37c0f8f5b50c7ae5d5a5ad897b2763fe5ebc60da6195b71478da` |

Accepted specification canonical `b3b5e7eb918622c7ca45761b9313cf266e29d12e81767af89ca3dd42465ec9bd`, plan `b6a1015ddeaf2c1a60689706f48d9a238d764c0f3854ca66449f82d4072d47b9`, R1 specification review `04aab5223e336739279dd4ab47d7c17e9e1c7e936e8ad123c672399f25fa6d2a` (same accepted documents as prior Task 1 review).

## Important finding: P2 — preserve unavailable diagnostics from partial source polls

Location: group_graph.py lines 322–346 and observe_results' false-proof classification. `_SourceReads` sets `failed` only when a call raises. Production GitHubSource.poll can successfully return valid unrelated bundles while recording a failed run/artifact fetch in `source.errors`. If the requested dependency's bundle is missing because of that failure, genuine verified_done returns false, but neither wrapper failed flag is true. observe_results therefore calls that dependency pending and evaluate_graph reports dependency_pending. The accepted design explicitly distinguishes not-yet-accepted from unreadable dependency_unavailable. This hides a real source failure behind a completion wait and loses the required operator-visible reason. It remains conservatively blocked; this finding is not an unsafe-ready bypass.

Independent reproduction used the test transport with all production verification code intact:

1. Create owner/repo Issues 1 (blocked_by owner/repo#2), 2 and 3; authorize 1; call transport.accept(2) and accept(3).
2. Replace only source transport so `/actions/artifacts/202/zip` raises OSError, while every other request delegates to the original transport.
3. Collect actual snapshot, call observe_results and evaluate_graph.
4. Observed source.errors contains run_id202/attempt1/head0000000000000000000000000000000000000002 with invalid GitHub response; Issue2 observation nevertheless says pending and Issue1 says dependency_pending. Issue3's valid bundle makes poll return normally.

Required correction: freeze/propagate production partial source error provenance within the same bounded refresh and map false verification caused by an unavailable relevant run/head to unavailable. Do not re-fetch mutable proof after verification, suppress errors, inject true completion, or make an unrelated valid dependency lose its accepted proof. Add a transport-only regression with one unavailable dependency artifact and another valid accepted result in the same repository, asserting dependency_unavailable for the affected consumer and preservation of independent valid work. Fresh independent review must bind revised bytes.

## Strengths

Typed contains edges do not become child-to-parent waits; explicit aggregate requires plus inverse wait produces a real cycle. Deterministic iterative SCC avoids recursion limits; downstream cycle and unavailable reasons remain conservative. Duplicate task IDs, missing cross-project sources, malformed dual declarations and node/edge overflow cannot yield ready partial graphs. Readable cross-project dependencies grant no execution route. Native aggregation requires explicit current projected children rather than arbitrary children or milestone inference.

The result observer invokes genuine production verified_done through read-only cached wrappers, then extracts the same lifecycle/artifact receipt without a second mutable fetch. It binds current snapshot, immutable Issue ID, task ID, receipt digest/identity and merge commit. Tests substitute HTTP transport only and exercise actual artifact digests, CI/merge ancestry and publisher/lifecycle validation; there is no true-returning verifier. No candidate pipeline execution imports, journal writes, GitHub mutations or source grants were introduced.

## Independent verification

Existing Python `C:/Users/sibiya666/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe`:

- `-m unittest tests.test_group_graph tests.test_dispatch_selection tests.test_project_worker -v`: **38 tests, OK, 0.316s** (14 new graph tests).
- Independent partial-source reproduction above: confirms P2 despite the green targeted suite.
- `-m unittest discover -s tests -v`: **488 tests, OK, 4 existing symlink-privilege skips, 108.435s**. Private full output: runtime TEMP `tt-groups-review-task2-full.log`. The passing existing suite does not cover or resolve the independently reproduced partial-source finding.

## Declined to judge

- Execution admission, task modes/open lifecycle, policy authority and per-effect graph revalidation remain existing/later host gates; graph ready is expressly a dependency report, not execution permission.
- Canonical journal ownership, reservations, durable observations, six-role stages and unattended refill belong to later gated integration tasks.
- Accepted-main source/base-update proof, PR/main barrier, installed pilot and whole-Issue acceptance are not implemented or claimed by this graph module.

These are explicit boundaries, not waived requirements. Issue16 exact-main CI, independent postmerge acceptance and automatic closure still gate all pipeline integration, followed by actual contract audit/revalidation. Reviewer writes only this requested report and private temporary verification output; no product/card/Task1-report change, commit, push, GitHub write or production journal/config mutation.

## R1 independent re-review — current binding

2026-11-02. Same independent reviewer, fresh review of the complete correction and its tests against the accepted Task 2 contract. **ACCEPTED for Task 2's pure graph and read-only production-observation boundary at the exact R1 product bytes below.** Original rejected binding and finding above are retained as history; their report's pre-append raw SHA-256 was independently confirmed as `de9be1a2171ca17d70d3f69d43a55b0fd762dddefa86378974abaf001491158b`. No actionable Critical, Important or Minor finding remains in this scope.

HEAD remains independently observed `fea86491410a0fecf83022ad8bf7cef3477a41d0`; the two product files remain untracked, so acceptance binds full raw bytes (canonical LF hashes are identical), not a committed diff:

| File | R1 SHA-256 |
| --- | --- |
| task_tower/group_graph.py | `46faad5102adf68047f93f64dccd4d4e37a00434266c641ae0734dbc157434ea` |
| tests/test_group_graph.py | `f6b125edf553597aa5dae52edd231a23bdb37e1e05db5f4558edb9b47152fdba` |

### P2 resolved

The source wrapper freezes bounded sanitized production poll errors with the same refresh's cached catalog. A failed genuine completion verification can now associate unavailable merge data with the captured receipt's exact run/attempt or merge-head identity and return unavailable plus fixed diagnostic provenance. These diagnostic candidates cannot prove acceptance; genuine verified_done remains mandatory, and already verified independent results are preserved. Lifecycle and downloaded receipt reads reuse the same cached observation rather than refetch mutable proof. The new regression exercises the original failure through real GitHubSource/verified_done for both Actions and local receipts; another valid accepted Issue, its consumer and independent open work survive the partial outage.

Independently reran the original transport-only failure for both receipt modes: dependency2 unavailable, its consumer dependency_unavailable, unrelated dependency3 accepted. Additional private probes checked unrelated run/head, changed attempt with unrelated head and fully unrelated identity do not acquire diagnostic matches; malformed Boolean/integer/zero/negative run IDs fail closed; raw private error text is excluded; changing underlying errors after cached poll does not change that refresh or issue another poll; a fresh wrapper sees a fresh error epoch. One preliminary private probe command had an unmatched-parenthesis syntax error before execution; the corrected complete command passed. No product/test edit was used for these probes.

### Fresh verification and limits

- `-m unittest tests.test_group_graph tests.test_dispatch_selection tests.test_project_worker -v`: **40 tests, OK, 0.340s**, including both new regression cases.
- Original reproduction and independent identity/cache/sanitization probes described above: PASS.
- Full-suite completion evidence is recorded in the final verification paragraph below.

All earlier explicit declined-to-judge boundaries remain. This accepts revised Task 2 policy/reporting code only; it does not accept runtime scheduling, capacity ownership, unattended work, whole-development/TEST, main/PR/postmerge or Issue18 completion. Issue16's exact-main integration gate remains mandatory. Changed product bytes invalidate this verdict. Reviewer appended only this re-review and private verification output; no source/card/Task1-report edits, GitHub writes, commit or push.

Final independent R1 full-suite verification: `-m unittest discover -s tests -v` completed **490 tests, OK, 4 existing symlink-privilege skips, 110.728s**. Private full output: runtime TEMP `tt-groups-review-task2-r1-full.log`. Both frozen R1 product hashes were rechecked, and the entire original rejected report prefix still hashes to `de9be1a2171ca17d70d3f69d43a55b0fd762dddefa86378974abaf001491158b`.
