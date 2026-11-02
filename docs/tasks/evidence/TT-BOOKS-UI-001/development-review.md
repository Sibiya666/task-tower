# Whole-implementation independent development review — TT-BOOKS-UI-001

Verdict: **REJECTED** for whole-implementation development acceptance. Reviewer `books_development_review`, distinct from implementers and prior task reviewers. Reviewed branch `feat/books-ui`, HEAD `b51ec0dd42904eee2a1107fe3e7447d06410a7a7`, against base `918554a1e7f6dec10f81a366c1dececa845ff072`, including the coordinator's pending documentation. This is not TEST, hardware/native, PR, exact-main, postmerge or Issue-closure acceptance. No product files, commits, pushes or running user application were changed by this reviewer.

## Actionable blockers

1. **P2 — Real unfinished task statuses cannot be selected in the status filter.** `overlay/web/books-view.js:18` hardcodes proposed/ready/active/blocked/done/unknown/source, but `task_tower/github_tasks.py:59` and the actual shared projection use open/in_progress/needs_input/awaiting_merge/awaiting_postmerge/postmerge_review/postmerge_failed. An independent actual Python `project_issue` → helper `_public` → real Edge DOM probe produced all seven statuses, and none appeared in the filter options. The supplied browser fixtures instead use active/blocked and therefore mask the contract mismatch. All records remain visible under All, but a person cannot filter any real unfinished lifecycle state. Populate choices from the authoritative supported status contract or validated snapshot values, preserve useful selected filters during progressive refresh, and add an integration regression using real projection output rather than invented status aliases. Include remote-state filtering if that is how the accepted status/state control is implemented.

2. **P2 — Existing public migration provenance is dropped between aggregate and overlay.** `task_tower/books.py:73` attaches bounded public `migrations`; `overlay/web/books-policy.js` explicitly preserves it and `overlay/web/books-view.js:27` displays it. However `task_tower/overlay_books.py:15,28` omits it from ENTRY_FIELDS, and the native `BooksBridge.Frame` entry-field allowlist also omits it. Independent Python probe confirmed a valid migration with number/source_sha256/status/issue_url present upstream is absent from the helper output. The dialog consequently says “Не записано” for recorded provenance, defeating the established compatibility requirement explicitly checked in the Task 3 R2 review. Carry this existing public field through both helper and host with its bounded known-key schema; never pass raw registry/private paths. Add an end-to-end producer/native/policy regression proving the public hash/status survive and unknown keys remain excluded.

Both findings are integration defects not contradicted by the prior accepted per-task scopes or current passing suites. Correct/retest and obtain fresh independent development acceptance for changed bindings.

## Review assessment

Read repository AGENTS, accepted design/plan and prior spec/task review history/current verdicts; reviewed the complete changed product modules, integration changes, test contracts and pending documentation. Assessed public projection, hierarchy/pagination, immutable library schema/version declarations, progressive identity/library-before-proof ordering, conservative completion semantics, process ownership/deadlines/late-output fencing, trusted native message/source admission, modal state/focus and truthful capability boundaries. No additional blocking security finding identified: native URL opening is configured-repository/exact-Project allowlisted, helper invocation is fixed and shell-free, errors are fixed diagnostics, source text uses textContent and CSP/connect-src none is retained. Library declaration accepted is independent from current verified task Done; new refresh invalidates old proofs. Existing native placement/activity code remains separate. Prior rejection/correction history remains preserved rather than replaced.

Pending documentation accurately separates fixture/browser/native/source/main gates and does not claim Issue23 accepted in main. Its status-filter and provenance promises need the product fixes above. Background execution/readiness is not claimed. Historical #15/#22 exact-main/closure statements were supplied by coordinator and were not reverified against GitHub in this local review.

## Fresh independent verification

- Cached absolute Python 3.12 runtime: `-m unittest tests.test_book_projection tests.test_book_library tests.test_overlay_books -q`: **23 tests PASS**, 0.084 seconds, exit 0.
- `node --test overlay/test-books-policy.cjs overlay/test-books-host.cjs overlay/test-books-browser.cjs`: **26/26 PASS**, 11.166 seconds, exit 0. Includes actual Edge DOM and compiled native boundary/helper lifecycle harness; does not exercise the actual composition application or OS keyboard routing.
- Independent `node overlay/runtime/books-development-probe.cjs`: exit 0; actual Python public projection supplied seven genuine unfinished task statuses to real Edge. Printed missingStatuses containing all seven and upstreamMigrationPresent true/helperMigrationPresent false. This is a diagnostic reproduction of both blockers, not a passing acceptance assertion. Temporary ignored runtime probe only; no product/test edits.
- Coordinator reports complete root CLI **453 tests OK, 4 skipped, 148.971s**, overlay Python **18 OK**, full Node **41 passed**, and independently reproduced native smoke exit 0. Those broader runs are reported evidence, not runs performed by this reviewer. Read the separate native-smoke review; did not rerun the user application or smoke.

## Mandatory unresolved native/integration gates

Actual hardware/OS Ctrl+B and genuine configured source observation in Books remain **PENDING/BLOCKING** for Task5/TEST/native acceptance. Coordinator reports an isolated real-config production-host build where Shift+F10 opens the menu but automated Ctrl+B does not open Books; Windows Graphics Capture times out and a manual user observation is pending. A synthetic DOM KeyB event in Edge or actual composition cannot settle this. Fixture PNGs demonstrate fixture rendering only. No genuine successful source-refresh observation in the Books UI has yet been demonstrated. Do not grant TEST/native or exact-main acceptance from this development report, screenshot fixtures or green tests. Exact-head/base PR acceptance, CI/mergeability, expected-head merge, exact-main independent postmerge and automatic Issue closure remain separate future gates.

## Exact reviewed manifest

All changed product, test, spec/plan, documentation and screenshot artifacts in base-to-working-tree scope are bound below, including the pending integration report. Excluded: mutable task card `docs/tasks/TT-BOOKS-UI-001.json`, this self-referential review, and earlier review reports under `docs/tasks/evidence/TT-BOOKS-UI-001/`. Their current verdicts were read as context, not treated as product authority. Runtime ignored artifacts are not product scope. Text SHA-256 normalizes UTF-8 BOM away and CRLF to LF; PNG SHA-256 is raw bytes. Manifest digest is SHA-256 of sorted `path<TAB>hash<LF>` UTF-8 lines: `66168d5d4c4d60efbc9dff62302a4d69d2e798ee373a832e2d51717be23f7bcc`. Changing any bound artifact invalidates this binding.

| File | SHA-256 |
| --- | --- |
| `AGENTS.md` | `38376a50ca739b947883dc09d76465927274f1d6bdd3b85541cfccbc748a80f9` |
| `README.md` | `ff19a49fb8900f16720525d921cae89d9632b68d94dcf1ca3ad381f5849b9746` |
| `docs/evidence/2026-11-01-overlay-books.md` | `b6fa106c38cb4841d531eb6c08007e20d469044717e770cb437ebbf038fac383` |
| `docs/evidence/2026-11-02-overlay-books-native-smoke.md` | `ac8e96b17f88d50ba20ff9f3bb108404df747e14537f45cac1c738f1194ef265` |
| `docs/github-books.md` | `519dec8fe36aeeeb7f52a73a60aa23ff4c03440e26231369ca1d89731bd28a81` |
| `docs/roadmap.md` | `aa38146e087666ce2e7a620082144ef46f2f6db85fc24e315ebe9251bf26efac` |
| `docs/screenshots/2026-11-02-books-native-fixture-overview.png` | `d903d2ba9d65d95ac9458480fb558b483e1c1fc8a6da54336ca00d64d700d7d8` |
| `docs/screenshots/2026-11-02-books-native-unavailable-compact.png` | `ae1061970092c965affab481bbe5685b7203b8e7fff639f1a71a3263d8585f2a` |
| `docs/superpowers/plans/2026-11-01-overlay-books.md` | `8f57f5d23934e250d5307da943675ddc57c674ff337d73f3494c3eef4d39f777` |
| `docs/superpowers/specs/2026-11-01-overlay-books-design.md` | `dc8b90a5284a320d3acafdfddf54c2aef3a95f6791a8941389f21c4213e8e426` |
| `overlay/BooksBridge.cs` | `0909ac2319e26b4befbb468181267c16ef5c40a0e0e7650596e4a713f6b5728d` |
| `overlay/README.md` | `8e3acb1f51c9a92c4ad7f935621cf9b719cc5d3acd11d5e333831907a834ac69` |
| `overlay/TowerHost.cs` | `b3f27c7e70be9ece489f9a22aef9049412403d70a1185610d9531c5c14fdaf97` |
| `overlay/run-html-overlay.ps1` | `32b59871334595b11099b531c3baef5ca818203e74c3e2013d90fd853670dc4e` |
| `overlay/test-books-browser.cjs` | `4534ff6e8372ecbd22c75c838bb0594bd6739255e688a631aeeae8caa8f2331c` |
| `overlay/test-books-host.cjs` | `a77453e715b9975d3e2361804f4b473f8783644eeee0c433a8ce20b05c04db73` |
| `overlay/test-books-policy.cjs` | `779003f71284c2122c2a1aba9849c81c10c35046063fc7dd41ebe6ccc90d69c0` |
| `overlay/web/books-policy.js` | `a73fa4b73cd81d6e8ae9524118f39458cad46febf535bdc6c8adad332d1eb507` |
| `overlay/web/books-view.js` | `e6519b7a0fbd4a8a15a4531a6b6acb119c8de1bda0290f543a9d4a7495edfbf4` |
| `overlay/web/books.css` | `5c9710611d412f61f6723761c5f4b71b8c0ec61b4cd1bf52b2916ff2d1421f58` |
| `overlay/web/index.html` | `a5bcbf661db2b7a85d80695d1dc39a3ada0c8eaed4fc37d225c1284e1bcdda77` |
| `overlay/web/world-view.js` | `b703cfdf765b8d455d32f2679f7f382b33c44bf2f382d4185fac9d7a572586b9` |
| `task_tower/book_library.py` | `2d15df2bc8595aa2b96fdfc9f255a6217b5836d5dec63d7235041d2b316f96db` |
| `task_tower/book_projection.py` | `d10f3b747db9ae2106a4c75794f15fb6708d398368f3490e829d2fe917bc3a1e` |
| `task_tower/books.py` | `ba38d0976361a797f7cc8acc50a18e6d727ae115e46c82a9b34c0b26804768c5` |
| `task_tower/github_tasks.py` | `9269064bdf9e1f50f62c7fb58339f7212850030b13a8953e590b499c3687117d` |
| `task_tower/overlay_books.py` | `50806c9fceef4a3d340036f0846cb87cf76ef9fc7ad274111ee867fd312f382d` |
| `tests/test_book_library.py` | `1c0e5afe013826081e61d237f9a283c623e40fd1f288ba407ab2d6e21f9fd5d9` |
| `tests/test_book_projection.py` | `ec776c5438ca4e714b60380f0ab3f87cc7de6891c2fac77a701f06a4c16f69cc` |
| `tests/test_github_projects.py` | `fac743f9dcef7c06d769eb774b5289f4e180425d0d824de4f4741e35fe4a3a40` |
| `tests/test_github_projects_acceptance.py` | `a9d4b88c253330cac4d24f0228dc82302253377ef8792ee4da3cbacb66f6cc55` |
| `tests/test_overlay_books.py` | `d23b775620ff132156c09fa61d56bd73ea555861abce31931e74d565582b5e0d` |
| `tests/test_publication_books.py` | `0fe005102d193795b1b1fdba7abfe5022bded1e56c6033c0ec51bc4ccaf00445` |

## R1 independent whole-implementation development re-review — current verdict

Verdict: **ACCEPTED for whole-implementation development/source-and-focused-regression scope**. This supersedes the original development rejection for the exact manifest below; the original findings and rejected binding remain preserved above. No unresolved blocking development finding remains. This is explicitly **not TEST, actual native keyboard/source, PR, exact-main, postmerge or Issue-closure acceptance**. Mandatory unresolved native/integration gates above remain pending.

Reviewed complete seven-file correction and rechecked the whole current base-to-working-tree scope against the accepted design/plan and prior review: only six prior bound files changed, plus the new `tests/books_overlay_fixture.py`; all other 27 original bound artifacts are byte/canonically unchanged, including TowerHost and pending documentation. HEAD remains `b51ec0dd42904eee2a1107fe3e7447d06410a7a7`, base `918554a1e7f6dec10f81a366c1dececa845ff072`. No product source edits, commit, push, native user application interaction or GitHub write by reviewer.

Both P2 defects are corrected. Status choices now include all validated snapshot statuses plus the retained selected status, so all seven real unfinished lifecycle states can be selected and an in-use filter survives an intermediate frame that temporarily omits matching records. The selector stays text-only and policy performs equality filtering; no lifecycle aliases or acceptance semantics are introduced. The real aggregate/lifecycle/private-registry fixture supplies actual producer output to Edge rather than inventing active/blocked states. Its test selects each real status, asserts matching records, retains awaiting_merge through disappearance/reappearance and displays recorded migration detail.

Helper migration projection now emits only number/source_sha256/status/issue_url, bounds records to 100 and validates positive integer/null identity, exact lowercase hash, known current/stale/pending state and source identity syntax. Native admits this field only with the exact four-key schema, bounded list, correct types/hash/state and exact repository-qualified Issue URL; unknown private keys are rejected by native and removed by helper. Existing JS known-key projection retains these fields. Shared fixture constructs a genuine temporary private migration registry, runs aggregate and unchanged lifecycle, then the helper public projection; its path, original content and registry-only identifiers do not reach output. Compiled native test admits this actual producer frame and rejects the private-key mutation. Migration provenance never grants Done or verifier success. Bounds/attempt ownership/source allowlist behavior remains intact.

Fresh independent verification from repository root:

- Cached absolute Python: `-m unittest tests.test_book_projection tests.test_book_library tests.test_overlay_books -q`: **25 PASS**, 0.130 seconds, exit 0.
- `node --test overlay/test-books-policy.cjs overlay/test-books-host.cjs overlay/test-books-browser.cjs`: **27/27 PASS**, 16.216 seconds, exit 0. Includes real producer-to-Edge integration, progressive selection preservation and actual compiled native producer-frame admission/privacy rejection.
- Independent stdin Python matrix (additional to submitted tests): rejects boolean/zero/string migration numbers, object/unknown states, mismatched Issue number, userinfo URL and uppercase/invalid hash; accepts valid null-number/null-URL pending record; strips unknown private keys without mutating input. **PASS**, exit 0.
- Independently recomputed all current hashes and compared against original manifest and supplied correction hashes: exactly the expected six prior files changed; new fixture hash matches supplied binding. No other bound product/documentation change.

Default execution initially failed Windows logon 1909 before running a process; authorized escalated read/test invocations succeeded. No credential/ACL/runtime/model/tool installation change. Actor-reported expected RED regressions were read as reported evidence, not independently recreated here. Complete root/overlay suite and actual native smoke reruns after R1 are coordinator-owned pending checks. Hardware/manual Ctrl+B and genuine source-refresh observation remain unresolved and cannot be inferred from these passing browser/native-boundary fixtures. Fresh full-diff exact-head/base PR and exact-main gates remain required after integration.

### R1 exact complete canonical manifest

Same exclusions and canonicalization convention as original manifest (mutable card, self-reference and earlier review reports excluded; text UTF-8 without BOM/LF, PNG raw). New fixture included. Sorted `path<TAB>hash<LF>` manifest SHA-256: `69250921c1eddd280270970ff77397b8a6743eb466e4c0072f3fba296791a2f7`. Changing a bound artifact invalidates this acceptance.

| File | SHA-256 |
| --- | --- |
| `AGENTS.md` | `38376a50ca739b947883dc09d76465927274f1d6bdd3b85541cfccbc748a80f9` |
| `README.md` | `ff19a49fb8900f16720525d921cae89d9632b68d94dcf1ca3ad381f5849b9746` |
| `docs/evidence/2026-11-01-overlay-books.md` | `b6fa106c38cb4841d531eb6c08007e20d469044717e770cb437ebbf038fac383` |
| `docs/evidence/2026-11-02-overlay-books-native-smoke.md` | `ac8e96b17f88d50ba20ff9f3bb108404df747e14537f45cac1c738f1194ef265` |
| `docs/github-books.md` | `519dec8fe36aeeeb7f52a73a60aa23ff4c03440e26231369ca1d89731bd28a81` |
| `docs/roadmap.md` | `aa38146e087666ce2e7a620082144ef46f2f6db85fc24e315ebe9251bf26efac` |
| `docs/screenshots/2026-11-02-books-native-fixture-overview.png` | `d903d2ba9d65d95ac9458480fb558b483e1c1fc8a6da54336ca00d64d700d7d8` |
| `docs/screenshots/2026-11-02-books-native-unavailable-compact.png` | `ae1061970092c965affab481bbe5685b7203b8e7fff639f1a71a3263d8585f2a` |
| `docs/superpowers/plans/2026-11-01-overlay-books.md` | `8f57f5d23934e250d5307da943675ddc57c674ff337d73f3494c3eef4d39f777` |
| `docs/superpowers/specs/2026-11-01-overlay-books-design.md` | `dc8b90a5284a320d3acafdfddf54c2aef3a95f6791a8941389f21c4213e8e426` |
| `overlay/BooksBridge.cs` | `49e48abab51e0aadffe1c2ae290fef513ce782a80487832fa6bf3a02946cffd2` |
| `overlay/README.md` | `8e3acb1f51c9a92c4ad7f935621cf9b719cc5d3acd11d5e333831907a834ac69` |
| `overlay/TowerHost.cs` | `b3f27c7e70be9ece489f9a22aef9049412403d70a1185610d9531c5c14fdaf97` |
| `overlay/run-html-overlay.ps1` | `32b59871334595b11099b531c3baef5ca818203e74c3e2013d90fd853670dc4e` |
| `overlay/test-books-browser.cjs` | `5d9fe4ab27b62543f550a24d3c882818d2aa62e7af9642b6888b29e15ad8396b` |
| `overlay/test-books-host.cjs` | `1d94bb4ea7ab20d225ae780c718177092f44c6fdd9bc376d6eee73ca9203ddd4` |
| `overlay/test-books-policy.cjs` | `779003f71284c2122c2a1aba9849c81c10c35046063fc7dd41ebe6ccc90d69c0` |
| `overlay/web/books-policy.js` | `a73fa4b73cd81d6e8ae9524118f39458cad46febf535bdc6c8adad332d1eb507` |
| `overlay/web/books-view.js` | `3acce53ef452d2a3136f0b71c3b40ee23509edec4112e813466b1ab0ac510a95` |
| `overlay/web/books.css` | `5c9710611d412f61f6723761c5f4b71b8c0ec61b4cd1bf52b2916ff2d1421f58` |
| `overlay/web/index.html` | `a5bcbf661db2b7a85d80695d1dc39a3ada0c8eaed4fc37d225c1284e1bcdda77` |
| `overlay/web/world-view.js` | `b703cfdf765b8d455d32f2679f7f382b33c44bf2f382d4185fac9d7a572586b9` |
| `task_tower/book_library.py` | `2d15df2bc8595aa2b96fdfc9f255a6217b5836d5dec63d7235041d2b316f96db` |
| `task_tower/book_projection.py` | `d10f3b747db9ae2106a4c75794f15fb6708d398368f3490e829d2fe917bc3a1e` |
| `task_tower/books.py` | `ba38d0976361a797f7cc8acc50a18e6d727ae115e46c82a9b34c0b26804768c5` |
| `task_tower/github_tasks.py` | `9269064bdf9e1f50f62c7fb58339f7212850030b13a8953e590b499c3687117d` |
| `task_tower/overlay_books.py` | `5d05cc1da6c6df815b0b212122856b065d9d521d63c0f046ebe1658e8cdc4480` |
| `tests/books_overlay_fixture.py` | `40827bd4adc19a48b58e6f215735ee863485092fc550f6a063fa1f1853fae7a4` |
| `tests/test_book_library.py` | `1c0e5afe013826081e61d237f9a283c623e40fd1f288ba407ab2d6e21f9fd5d9` |
| `tests/test_book_projection.py` | `ec776c5438ca4e714b60380f0ab3f87cc7de6891c2fac77a701f06a4c16f69cc` |
| `tests/test_github_projects.py` | `fac743f9dcef7c06d769eb774b5289f4e180425d0d824de4f4741e35fe4a3a40` |
| `tests/test_github_projects_acceptance.py` | `a9d4b88c253330cac4d24f0228dc82302253377ef8792ee4da3cbacb66f6cc55` |
| `tests/test_overlay_books.py` | `94d3ae3789c7dde18c6aed1844a7b9675d440bbb42d2e4fc3617aa7eb3774f01` |
| `tests/test_publication_books.py` | `0fe005102d193795b1b1fdba7abfe5022bded1e56c6033c0ec51bc4ccaf00445` |

## R2 independent test-only rebind — current verdict

Verdict: **ACCEPTED for whole-implementation development/source-and-focused-regression scope** at the complete manifest below. R1 acceptance is retained with the single updated test binding; original rejected findings and correction history remain preserved. No unresolved blocking development finding. This is not TEST/hardware/genuine-source, PR, main/postmerge or Issue-closure acceptance. HEAD `ba125ca4d054333e736a5c2a7348124257e9b3b6`, original base `918554a1e7f6dec10f81a366c1dececa845ff072`.

Independently inspected the entire delta since R1 commit ba125ca: one test-only ProcessStartInfo initializer now sets `WorkingDirectory=rootDir`. The root is already derived from Node __dirname and passed to the compiled harness, so the real producer fixture imports from the canonical repository root regardless of the invoking shell directory. No assertion is removed or weakened, and no product behavior changes. This corrects the documented-overlay-cwd failure independently reproduced by the native reviewer; my R1 checks ran from root and did not expose that portability failure.

Fresh independent command from overlay: `node --test test-books-host.cjs`: **2/2 PASS**, 7.521 seconds, exit 0, including compiled native migration admission/privacy and helper lifecycle checks. Independently recomputed all 34 R1 manifest hashes: exactly overlay/test-books-host.cjs changed; all other 33 bound artifacts, including every product source and pending product documentation, remain unchanged. Corrected test raw SHA-256 `e9be6f93c1b1dfd60e0596b2bf0f711c4a52ecc7bd039ae7e9e76f41ddfa1876`, canonical `fd29a98e3310dd3f7d1bed6f3248fc1fd031a8160d17d6e24ca8595a692f7147`, match supplied values.

Read the separate native review R2: it reports its own fresh root/overlay boundary runs and full documented Node **42/42 PASS**, retaining independently rerun R1 actual composition smoke against unchanged product hashes. Coordinator reports R1 full root CLI **455 tests OK, 4 skipped, 138.231 seconds**. Those broader/native runs were not repeated by me for this test-only insertion. Hardware/manual keyboard routing and genuine configured UI refresh remain pending; Issue23 needs_input/awaiting-user status is coordinator-reported rather than independently queried. This review grants no closure authority. No product edits, commit, push, GitHub write or desktop interaction by reviewer.

### R2 exact complete canonical manifest

Same exclusions/canonicalization as prior manifests. SHA-256 of sorted `path<TAB>hash<LF>`: `871f1e34457e6126a6d696ba2c463bed3ec1f9449682e9435f6b321be6d5085d`. Changing a bound artifact invalidates this acceptance.

| File | SHA-256 |
| --- | --- |
| `AGENTS.md` | `38376a50ca739b947883dc09d76465927274f1d6bdd3b85541cfccbc748a80f9` |
| `README.md` | `ff19a49fb8900f16720525d921cae89d9632b68d94dcf1ca3ad381f5849b9746` |
| `docs/evidence/2026-11-01-overlay-books.md` | `b6fa106c38cb4841d531eb6c08007e20d469044717e770cb437ebbf038fac383` |
| `docs/evidence/2026-11-02-overlay-books-native-smoke.md` | `ac8e96b17f88d50ba20ff9f3bb108404df747e14537f45cac1c738f1194ef265` |
| `docs/github-books.md` | `519dec8fe36aeeeb7f52a73a60aa23ff4c03440e26231369ca1d89731bd28a81` |
| `docs/roadmap.md` | `aa38146e087666ce2e7a620082144ef46f2f6db85fc24e315ebe9251bf26efac` |
| `docs/screenshots/2026-11-02-books-native-fixture-overview.png` | `d903d2ba9d65d95ac9458480fb558b483e1c1fc8a6da54336ca00d64d700d7d8` |
| `docs/screenshots/2026-11-02-books-native-unavailable-compact.png` | `ae1061970092c965affab481bbe5685b7203b8e7fff639f1a71a3263d8585f2a` |
| `docs/superpowers/plans/2026-11-01-overlay-books.md` | `8f57f5d23934e250d5307da943675ddc57c674ff337d73f3494c3eef4d39f777` |
| `docs/superpowers/specs/2026-11-01-overlay-books-design.md` | `dc8b90a5284a320d3acafdfddf54c2aef3a95f6791a8941389f21c4213e8e426` |
| `overlay/BooksBridge.cs` | `49e48abab51e0aadffe1c2ae290fef513ce782a80487832fa6bf3a02946cffd2` |
| `overlay/README.md` | `8e3acb1f51c9a92c4ad7f935621cf9b719cc5d3acd11d5e333831907a834ac69` |
| `overlay/TowerHost.cs` | `b3f27c7e70be9ece489f9a22aef9049412403d70a1185610d9531c5c14fdaf97` |
| `overlay/run-html-overlay.ps1` | `32b59871334595b11099b531c3baef5ca818203e74c3e2013d90fd853670dc4e` |
| `overlay/test-books-browser.cjs` | `5d9fe4ab27b62543f550a24d3c882818d2aa62e7af9642b6888b29e15ad8396b` |
| `overlay/test-books-host.cjs` | `fd29a98e3310dd3f7d1bed6f3248fc1fd031a8160d17d6e24ca8595a692f7147` |
| `overlay/test-books-policy.cjs` | `779003f71284c2122c2a1aba9849c81c10c35046063fc7dd41ebe6ccc90d69c0` |
| `overlay/web/books-policy.js` | `a73fa4b73cd81d6e8ae9524118f39458cad46febf535bdc6c8adad332d1eb507` |
| `overlay/web/books-view.js` | `3acce53ef452d2a3136f0b71c3b40ee23509edec4112e813466b1ab0ac510a95` |
| `overlay/web/books.css` | `5c9710611d412f61f6723761c5f4b71b8c0ec61b4cd1bf52b2916ff2d1421f58` |
| `overlay/web/index.html` | `a5bcbf661db2b7a85d80695d1dc39a3ada0c8eaed4fc37d225c1284e1bcdda77` |
| `overlay/web/world-view.js` | `b703cfdf765b8d455d32f2679f7f382b33c44bf2f382d4185fac9d7a572586b9` |
| `task_tower/book_library.py` | `2d15df2bc8595aa2b96fdfc9f255a6217b5836d5dec63d7235041d2b316f96db` |
| `task_tower/book_projection.py` | `d10f3b747db9ae2106a4c75794f15fb6708d398368f3490e829d2fe917bc3a1e` |
| `task_tower/books.py` | `ba38d0976361a797f7cc8acc50a18e6d727ae115e46c82a9b34c0b26804768c5` |
| `task_tower/github_tasks.py` | `9269064bdf9e1f50f62c7fb58339f7212850030b13a8953e590b499c3687117d` |
| `task_tower/overlay_books.py` | `5d05cc1da6c6df815b0b212122856b065d9d521d63c0f046ebe1658e8cdc4480` |
| `tests/books_overlay_fixture.py` | `40827bd4adc19a48b58e6f215735ee863485092fc550f6a063fa1f1853fae7a4` |
| `tests/test_book_library.py` | `1c0e5afe013826081e61d237f9a283c623e40fd1f288ba407ab2d6e21f9fd5d9` |
| `tests/test_book_projection.py` | `ec776c5438ca4e714b60380f0ab3f87cc7de6891c2fac77a701f06a4c16f69cc` |
| `tests/test_github_projects.py` | `fac743f9dcef7c06d769eb774b5289f4e180425d0d824de4f4741e35fe4a3a40` |
| `tests/test_github_projects_acceptance.py` | `a9d4b88c253330cac4d24f0228dc82302253377ef8792ee4da3cbacb66f6cc55` |
| `tests/test_overlay_books.py` | `94d3ae3789c7dde18c6aed1844a7b9675d440bbb42d2e4fc3617aa7eb3774f01` |
| `tests/test_publication_books.py` | `0fe005102d193795b1b1fdba7abfe5022bded1e56c6033c0ec51bc4ccaf00445` |

## Current-head independent development revalidation — 2026-11-02

Fresh reviewer `/root/pr_reviewer_review`, distinct from authors, accepts current whole Issue23 development scope at HEAD `5b90ff423696396a871df1e27599c8cde489da2c`, base/origin-main `918554a1e7f6dec10f81a366c1dececa845ff072`. Local `main` is stale and was not used to define Issue23 scope. Inspected the complete actual 45-file Issue23 diff, additive shared Python/GitHub projection, library index, bounded helper/native bridge, policy/view/CSS, launcher, native event routing, tests and documentation; reviewed prior rejected/corrected histories rather than treating their verdicts as current acceptance.

No blocking development finding remains. This revalidates R2 plus final native shortcut correction; it grants no PR/main/postmerge/closure acceptance. The native callback queues fixed script execution and checks exact document/readiness after callback return; no synchronous Source COM getter, source/CSP/network/credential or scene-state relaxation. See native-keyboard-review.md for independently executed final native smoke and27 focused tests, and test-review.md for whole-stage evidence. Historical manual failures remain; coordinator subsequently records the user's final physical Ctrl+B success. Genuine connected UI source was observed as partial/fresh/last-success-unknown, never full verified refresh success.

Independently recomputed all34 R2 manifest paths with its UTF-8-sig decode, CRLF/CR→LF, UTF-8 hashing for text and raw PNG bytes. Exactly TowerHost.cs differs; its current canonical hash is `c4e52322835c121a1003570da30a9c9b33eb5eb15a86d7baf72a80a8a348ba3b`, raw `adb87c95d8b13ba9ef0e065243974ca14838d589359ca9e3b914a7b21502765a`. All33 other table bindings above remain identical. Thus this is the complete34-file R2 table with only that explicit replacement; SHA-256 of sorted path<TAB>hash<LF> is `bbff926c4f95767333897504791b92bca5bd7bf0a4df07af90f282eeb9572989`. The scoped native review uses BOM-retaining LF hash `7cecb03f50f1918ea0a9e2b70acc9ee8038d848dcfec9beaf9bb379c637b2832`; these explicitly different schemes refer to the same raw source bytes.

Fresh independent complete overlay Python18tests passed6.162s and documented complete Node42tests passed23.095549s, no Node skips. Final native composition smoke independently returned0. Full CLI result is recorded in the separate test review. No product edits, commits, pushes or live external writes by reviewer; only requested acceptance evidence was written. Three historical added blank lines at EOF in books-view.js/test_book_library.py/test_book_projection.py are diff-check whitespace warnings, not behavior or security findings.

## Current-head test-fixture-only rebind — 2026-11-02

Fresh reviewer `/root/pr_reviewer_review` accepts the exact test-only correction at HEAD `616d22606d685c4f587d2024b9ed2c5ca606b05c`. Inspected the entire delta since5b90ff4: only the positive temporary config/checkout root and corresponding privacy assertion in tests/test_overlay_books.py changed. Canonicalization precedes guarded input use; timeout/barrier/pending/final assertions, production paths/guards and skips are unchanged. Author junction RED/GREEN and coordinator acceptance are recorded separately in macos-fixture-review.md. Independently ran `python.exe -m unittest tests.test_overlay_books -q`:9tests0.157s, OK, exit0.

Raw test SHA-256 `d4e5230965fe67143aac738d01550dc5c0778bc022de7a3588015dcf387657d9`; existing development manifest UTF-8-sig/LF canonical SHA-256 `939763125a5a2283be58997e8b62649898c4916ae6d4fbf48c8b844885d0c136`. Independently rebound all34paths: exactly that test differs from prior current-head acceptance; TowerHost remains the accepted final native fix and all other32bindings remain identical. Complete R2 table with the current TowerHost and this test replacement hashes to sorted path<TAB>hash<LF> SHA-256 `e803c1b032406c8fac7d509093a41c944304c20fb26cef733596ef6fb97f5218`.

Current whole development acceptance remains valid with these explicit replacements. Whole TEST stage remains PENDING until current exact-head three-OS CI is successful; local focused GREEN does not substitute for macOS. No product edits, commits, pushes or live external writes by reviewer. Prior verdicts and complete local455/18/42/native evidence remain preserved.
