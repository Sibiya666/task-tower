# Overlay Books integration evidence

Issue: `Sibiya666/task-tower#23`; task: `TT-BOOKS-UI-001`. Source base: `918554a1e7f6dec10f81a366c1dececa845ff072`. This report distinguishes implementation tests from final independent acceptance. It does not close the Issue or assert exact-main completion.

## Accepted implementation boundaries

Independent task reports are under `docs/tasks/evidence/TT-BOOKS-UI-001/`. Projection/library, native bridge, pure hierarchy policy and modal interaction were reviewed separately. Their current reports retain earlier rejected findings and their corrections. Commits: `1d5a9b8` (projection), `ee7bd4a` (policy), `ec2dcdd` (bridge), `dc3cf32` (view), `a60bd1d` (physical KeyB handling under non-English layouts).

The unchanged completion verifier remains the authority for accepted task progress. Closed Issues, declared artifact states and pending refresh results cannot produce accepted completion. Identity/library frames precede expensive verification; previous-refresh proof is invalidated rather than cached as current proof.

## Coordinator integration checks

Runtime: bundled Python 3.12.14 at `C:/Users/sibiya666/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe`; Node 24.22.1; existing installed Edge and WebView2. No runtime installation or model choice was performed.

From `overlay/`, `python -m unittest -q`: **18 tests, 3.796 seconds, OK**.

From `overlay/`, `node --test test-web.cjs test-room-skins.cjs test-presence.cjs test-presence-browser.cjs test-scene-position.cjs test-session-light.cjs test-tower-arrivals.cjs test-world-policy.cjs test-world-browser.cjs test-visual-audit.cjs test-books-policy.cjs test-books-host.cjs test-books-browser.cjs`: **41 tests, 41 passed, 0 failed, 24.334 seconds**. Browser fixtures demonstrate UI contracts rather than real GitHub or native hardware input.

From the repository root, `python -m unittest discover -s tests -q`: **453 tests, 148.971 seconds, OK, 4 skipped**. The skips concern existing platform/privilege boundaries, not a replacement for native Books acceptance.

## Actual Windows composition

See [native smoke evidence](2026-11-02-overlay-books-native-smoke.md) for the exact smoke-only source binding, actual Windows PowerShell 5.1 command, exit 0, assertions and raw CoreWebView2 captures. The coordinator also viewed both images. The overview displays literal malicious-looking text with pending verification despite closed remote state; the compact unavailable state fits the modal horizontally with internal scrolling.

These screenshots contain deterministic public fixture/unavailable data. Synthetic DOM key events in actual composition are explicitly separate from physical keyboard acceptance. They do not establish live GitHub refresh.

## Remaining acceptance gates

An isolated test executable compiles the production host/bridge without changes, bypasses only the global single-window lookup through a test entry point and uses a unique test caption. Its real private connection is never published. The computer-use tool was explicitly authorized for this application. UI Automation reads the actual tower and opens the world menu with Shift+F10, but automated Ctrl+B has not opened Books and Windows Graphics Capture times out. The coordinator requested a manual keyboard observation. Neither app-access approval nor synthetic smoke is counted as that observation.

The separate [independent smoke review](../tasks/evidence/TT-BOOKS-UI-001/task5-native-review.md) accepted the exact smoke change after its own actual native run and image inspection. Actual keyboard/source-refresh observation, whole-diff development/test acceptance, exact head/base PR review and CI, expected-head merge, exact-main postmerge acceptance and automatic closure remain separately required. No fixture receipt or manual Issue closure substitutes for these gates.
