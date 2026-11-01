# Task 4 independent UI spec and code-quality review

Verdict: **REJECTED**. Reviewed frozen working-tree five-file diff over HEAD ec2dcdd on feat/books-ui. Task 1/2/3 accepted contracts and current design/plan inspected. No product source edits or commits by reviewer. This is neither PR acceptance nor Task 5 native UI acceptance.

## Blocking findings

1. **P2: Freshness label never expires while dialog stays open.** books-view.js calculates health only during render; no clock-driven refresh updates it. Independent real Edge probe opened dialog, delivered final ready frame with current fetched_at, advanced Date.now by 301 seconds, and observed BooksPolicy.isStale true while visible health still said `ready · Данные свежие`. Subsequent user interaction eventually updates it, but passive inspection falsely claims freshness past the explicit 300-second boundary. Add clock-aware health updates and browser coverage.
2. **P2: Removed selected record silently disappears.** acceptSnapshot clears selection when the new frame omits its identity, then renders the ordinary list. Independent Edge probe selecting o/r#1 then delivering entries:[] showed only the generic empty-filter message, with no removed/unavailable selected identity. Accepted design explicitly requires refresh to label a removed selection unavailable. Preserve an explicit unavailable-selection presentation while retaining valid filters/page behavior.
3. **P2: Missing and unavailable detail states are not presented as required.** renderDetail only emits fields that exist, so absent description/phase/blockers/results/history vanish rather than displaying `Не записано`. Unavailable relationships are raw JSON `{status:unavailable}`, and null phase says `не указан`; these do not implement the accepted known-missing versus failed-retrieval labels (`Не записано` / `Недоступно`). Independent minimal valid issue DOM probe confirms omitted detail labels. Present explicit stateful fields and add browser assertions for missing versus unavailable.
4. **P2: Relationship source references lose navigation.** Policy supplies row.source for unloaded/filtered parent/child references, but view renders every reference as a paragraph containing reason/id only. Users cannot open those supplied GitHub sources, contrary to source-linked relationship-reference design. Route validated reference source buttons through the same fixed native books-open-source action; unknown URLs remain inert. Add browser coverage including a filtered parent and unloaded child and exact native action assertions.

## Fresh verification

`node --test test-books-browser.cjs test-books-policy.cjs test-books-host.cjs test-world-browser.cjs test-presence-browser.cjs test-scene-position.cjs` from overlay: **24/24 PASS**, exit 0. This includes four actual Edge browser cases and compiled native boundary harness, not actual composition host interaction. Independent additional Edge stdin probes exited 0 and printed the discrepant states above; supplied passing tests do not assert these requirements.

Inspected the entire five-file source diff, DOM textContent construction, fixed action emission, native-only external opening, unchanged CSP/connect-src none and script ordering, modal capture/inert background suppression, focus trap/context-key suppression, page quota via accepted policy and declaration-versus-verified displays. Source does not mutate collector/session state or native placement; no TowerHost/tower.js changes. Browser tests cover hostile inert description, unknown source, allowed action, three books/project filter/grouping/status done, pending/new-refresh proof invalidation, narrow layout and focus restoration. Missing cases above prevent acceptance despite those passing checks.

Visually inspected fresh local runtime/books-narrow-list.png and runtime/books-narrow-detail.png using view_image. At 340x300 the opaque dialog remains within transparent window, long immutable identity wraps and controls fit width; screenshots show a scrolled detail/list viewport and cannot alone prove every lower action reachable. Existing test asserts no horizontal overflow and successfully operates lower controls. No permanent toolbar was added. Actual Windows composition open/close/focus and raw native UI screenshot remain mandatory Task 5 gates; compiled host tests and browser evidence do not satisfy them.

Platform default exec fails with account lock 1909; approved require_escalated read/test calls worked. No account, credential, ACL, package installation or personal desktop interaction performed.

## Canonical UTF-8/LF SHA-256 binding

- overlay/web/books-view.js: 270206ca780d27c43b3575f68894e9a007a8a71c65033ee734fe777337828248
- overlay/web/books.css: 5c9710611d412f61f6723761c5f4b71b8c0ec61b4cd1bf52b2916ff2d1421f58
- overlay/test-books-browser.cjs: 2c7dbea84546adee2a1e91697e9f796aa036870833114f7c02571dc0477a152f
- overlay/web/index.html: c480d9ef44ec9be60c88108df48b12b9832c6ad861e20b40e35d8463ec228511
- overlay/web/world-view.js: f1330339fe9ac98d703a543cd2cd24c00c818640eefe7b78c0cd668757b80f9c

Changing any bound source invalidates this verdict binding; fresh independent re-review required after correction.

## R1 independent re-review (current verdict)

Verdict: **ACCEPTED for Task 4 source/browser scope**. This supersedes the original rejected binding above; all four blockers are corrected. It is not whole-diff PR, merge/postmerge, or actual Windows composition UI acceptance. Task 5 remains mandatory.

Independently read the full revised view and browser-test sources and checked the retained five-file integration scope against the accepted policy/host/projection contracts. Health now updates its own text on a 1000ms modal-owned interval plus visibility change, without rerendering/focus movement or refresh messages; close clears the interval. Removed immutable selection remains explicitly unavailable until Back; subsequent list rendering clamps page. Detail presentation distinguishes omitted/null/empty fields from unavailable relationship objects. Filtered/unloaded relationship sources use fixed native action only after the same URL restriction, with unknown URLs inert. Existing three-card policy, filter controls, safe text, background suppression, Ctrl+B/menu entry, focus trap/Escape and live snapshot semantics are preserved.

Fresh independent command from overlay: `node --test test-books-browser.cjs test-books-policy.cjs test-books-host.cjs test-world-browser.cjs test-presence-browser.cjs test-scene-position.cjs`: **28/28 PASS**, exit 0 (eight real Edge Books tests). Added tests directly reproduce all four original findings and assert their required corrected behavior, including passive stale expiry without network/action/focus change, missing selected identity/page clamp, per-field missing/unavailable labels, filtered parent/unloaded child source actions and unknown-source inertness.

Independent additional real Edge probe instrumented only 1000ms intervals, performed three open/repeated-Ctrl+B/close cycles, asserted exactly one health timer while open and zero after each close, and monitored requests: **PASS**, exit 0, no HTTP(S) request. This checks interval ownership and no duplicate timer leak independently of the submitted tests. Inspected newly regenerated runtime/books-narrow-list.png and runtime/books-narrow-detail.png with view_image: 340x300 dialog width, wrapped version identity and readable controls remain intact. No source edits or commit by reviewer. Complete CLI/overlay integration remains coordinator-owned; native compiled harness is not actual composition UI evidence.

Canonical UTF-8/LF SHA-256 independently recomputed:

- overlay/web/books-view.js: 33a0762a0a7b8b61950f79dda60956f333ae244fe26e00adf932317e6ac05753
- overlay/web/books.css: 5c9710611d412f61f6723761c5f4b71b8c0ec61b4cd1bf52b2916ff2d1421f58
- overlay/test-books-browser.cjs: d374ae8dad80ca7482698e4d119b9e085ccd3246a9d61ae4d1e68c68b9ce875a
- overlay/web/index.html: a5bcbf661db2b7a85d80695d1dc39a3ada0c8eaed4fc37d225c1284e1bcdda77
- overlay/web/world-view.js: b703cfdf765b8d455d32f2679f7f382b33c44bf2f382d4185fac9d7a572586b9

Changing any bound source invalidates this acceptance. No unresolved blocking findings in the reviewed Task 4 source/browser scope.
