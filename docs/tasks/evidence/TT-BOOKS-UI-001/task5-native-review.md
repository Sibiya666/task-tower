# Task 5 independent native-smoke review

Verdict: **ACCEPTED for the smoke-only addition and submitted fixture evidence** (2026-11-02). Reviewer: books_native_smoke_review, distinct from author. Base HEAD `a60bd1d6c0a24d10f467f991d9ed105b0461fd96`. No blocking finding in this scope. This is not full Task 5, genuine-source, hardware-keyboard, PR, main or human acceptance.

Read repository AGENTS, accepted design/plan and Task 1–4 review history/current verdicts. Reviewed the complete TowerHost diff and native-smoke report. Changes are confined to SmokeBooksAssert/SmokeBooks, their call/result in existing SmokeTest, plus a UTF-8 BOM on the first line. Fixture injection is reachable only through the existing smoke branch. Production initialization, native message admission, rendering and source-opening behavior are unchanged.

## Independently reproduced evidence

From overlay, ran `C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe -NoProfile -ExecutionPolicy Bypass -STA -File overlay.ps1 -SmokeTest` with approved elevated execution: exit **0**. Separate version query reports **5.1.19041.6456**. Launcher uses cached absolute Python path and actual WPF WebView2CompositionControl. Fresh runtime result and PNG timestamps were 2026-11-02 00:04:22–23 +03:00; read both newly written result files. They report PASS for Books and existing transparent native smoke. This was a new isolated smoke process; no running user app was stopped or modified.

Inspected actual assertions: native PostWebMessageAsJson partial fixture renders a pending record despite remote closed; detail HTML-looking string stays text without image node; synthetic DOM Ctrl+B opens and focuses; Escape closes detail first then dialog with pin focus restoration; Tab and Shift+Tab exercise boundary trapping; synthetic Shift+F10 exposes the actual scene menu and its Books action opens the dialog. Native production opener rejects lookalike host; isolated production bridge accepts exact configured Issue through recording delegate and rejects disconnected repo without launching browser. Deliberately nonexistent executable genuinely exercises helper launch failure through bridge to unavailable view. Compact opening preserves native bounds and fits horizontal width. Existing pin, transparent body/native background and capture alpha pixel, monitor clamp, overview restoration and wide-window assertions pass before Books.

Viewed both submitted raw PNGs and both independently regenerated runtime PNGs with view_image. Overview shows literal malicious-looking text, pending verification, remote closed, partial health and readable internally scrolling detail. Compact 340x300 shows unavailable/stale/unknown last success with readable controls and vertical scrolling; lower controls require scroll. Both have clear outer corners around intentional opaque book surface. CapturePreviewAsync captures actual embedded WebView2 pixels; no desktop or postprocessing is used. Fresh overview bytes exactly match submitted overview. Fresh compact SHA differs (runtime `d68c279a4a875aead95197e6c5a7d3c42fc2863e1b0530a273cc208a3661b30d`), while visually matching unavailable compact presentation; submitted original remains preserved.

These handler events are synthetic and cannot demonstrate OS key routing or physical keyboard layout. The report states that limitation accurately. Genuine configured source refresh and actual Windows keyboard exercise remain coordinator-owned pending gates; the reported actual Ctrl+B problem must not be dismissed based on this passing smoke. No fixture receipt implies task acceptance or Issue completion.

## Exact bindings

Raw SHA-256 (reviewer independently verified):

- overlay/TowerHost.cs: `4085e3d5bde01fbe4ac9df1d9db642736904106844495f1b1e921169d9b4f820`
- docs/evidence/2026-11-02-overlay-books-native-smoke.md: `ac8e96b17f88d50ba20ff9f3bb108404df747e14537f45cac1c738f1194ef265`
- docs/screenshots/2026-11-02-books-native-fixture-overview.png: `d903d2ba9d65d95ac9458480fb558b483e1c1fc8a6da54336ca00d64d700d7d8`
- docs/screenshots/2026-11-02-books-native-unavailable-compact.png: `ae1061970092c965affab481bbe5685b7203b8e7fff639f1a71a3263d8585f2a`

Canonical UTF-8 without BOM/LF SHA-256:

- overlay/TowerHost.cs: `b3f27c7e70be9ece489f9a22aef9049412403d70a1185610d9531c5c14fdaf97`
- native-smoke report: `ac8e96b17f88d50ba20ff9f3bb108404df747e14537f45cac1c738f1194ef265`
- design: `dc8b90a5284a320d3acafdfddf54c2aef3a95f6791a8941389f21c4213e8e426`
- plan: `8f57f5d23934e250d5307da943675ddc57c674ff337d73f3494c3eef4d39f777`

Changed bound source/evidence invalidates this scoped verdict. Reviewer wrote only this review; no product edit, commit, push, external-source browser launch or desktop automation. An auxiliary hash command initially hit the WindowsApps Python alias; canonical hashes were then successfully computed with .NET SHA256 and UTF8Encoding, independent of that alias failure.

## R1 native rebind (current verdict)

**Native composition smoke ACCEPTED at the revised bindings below; overall R1 verification REJECTED pending the documented-overlay-cwd harness correction.** Independent actual WinPS 5.1 smoke exited 0 with fresh runtime PASS outputs at 2026-11-02 00:14:30 +03:00. Viewed both fresh actual CoreWebView2 captures: overview and compact match submitted original SHA-256 respectively `d903d2ba9d65d95ac9458480fb558b483e1c1fc8a6da54336ca00d64d700d7d8` and `ae1061970092c965affab481bbe5685b7203b8e7fff639f1a71a3263d8585f2a`. Earlier smoke limitations remain in force.

Inspected revised helper migration projection and bridge's exact four-key migration validation. Independently ran compiled boundary harness from repository root: `node --test overlay/test-books-host.cjs`, exit 0, 2/2 passed including real public producer migration preservation and rejection of private migration field. However required plan/AGENTS command from overlay, `node --test test-books-host.cjs`, exited 1, 1/2 passed: `real producer migration frame admitted` assertion fails. New projection fixture uses `sys.path.insert(0,os.getcwd())` while its ProcessStartInfo lacks canonical WorkingDirectory, so repository tests package cannot import from overlay cwd. This is a test portability blocker for the required full overlay verification; root-only green does not satisfy the documented command. Reported to coordinator; reviewer made no test/product edit. Fix fixture working directory/import binding then rerun required command before accepting overall R1 verification.

TowerHost remains unchanged raw `4085e3d5bde01fbe4ac9df1d9db642736904106844495f1b1e921169d9b4f820`, canonical `b3f27c7e70be9ece489f9a22aef9049412403d70a1185610d9531c5c14fdaf97`. Revised bindings independently computed:

- overlay/BooksBridge.cs raw `494bb524fcec3636263d07915ebee66be5db08841e6d592ebf162915b74c8f15`, canonical `49e48abab51e0aadffe1c2ae290fef513ce782a80487832fa6bf3a02946cffd2`.
- task_tower/overlay_books.py raw `c56cabfcf52720e900e841881805f7fe7de64e8e1c741b794162e3bc78c01f16`, canonical `5d05cc1da6c6df815b0b212122856b065d9d521d63c0f046ebe1658e8cdc4480`.

Inspected native smoke keyboard payload: it only emits English key `b`, physical code `KeyB`, Ctrl true. No non-English key/KeyB synthetic native event is exercised. Thus non-English native synthetic coverage is absent, and all hardware routing/layout acceptance remains pending regardless of browser regression coverage. Actual Ctrl+B issue must be independently resolved/manual-verified; synthetic success cannot dismiss it. No desktop automation, product changes, commit or push. Initial default read failed with account lock 1909; approved execution context succeeded.

## R2 test-working-directory correction (current verdict)

**ACCEPTED for native-smoke/boundary verification scope.** This supersedes the R1 documented-overlay-cwd blocker only, preserving its reproduced failure above. Reviewed exact one-line test-only change: harness Start now sets WorkingDirectory=rootDir, whose value is supplied from Node path.dirname(__dirname), matching canonical repository-root production helper behavior. No weakened assertion or product change. Independently verified unchanged raw hashes for TowerHost, BooksBridge and overlay_books.py against R1 above; therefore retained independent actual WinPS 5.1 composition execution and visual evidence from R1 still bind this product revision. No redundant native smoke was run after this test-only fix.

Fresh independent verification:

- Repository root `node --test overlay/test-books-host.cjs`: exit 0, 2/2 PASS (7368.2985ms).
- Overlay `node --test test-books-host.cjs`: exit 0, 2/2 PASS (7091.998ms), reproducing correction of exact R1 trigger.
- Overlay full documented Node command `node --test test-web.cjs test-room-skins.cjs test-presence.cjs test-presence-browser.cjs test-scene-position.cjs test-session-light.cjs test-tower-arrivals.cjs test-world-policy.cjs test-world-browser.cjs test-visual-audit.cjs test-books-policy.cjs test-books-host.cjs test-books-browser.cjs`: exit 0, **42/42 PASS**, 18833.49ms. Includes compiled bridge migration privacy/preservation and actual Python projection browser contract.

Corrected overlay/test-books-host.cjs SHA-256 raw `e9be6f93c1b1dfd60e0596b2bf0f711c4a52ecc7bd039ae7e9e76f41ddfa1876`, canonical UTF-8 no BOM/LF `fd29a98e3310dd3f7d1bed6f3248fc1fd031a8160d17d6e24ca8595a692f7147`, independently recomputed. R1 product bindings above remain current. No unresolved blocking finding in this scoped native-smoke/boundary review. Actual hardware/non-English native key routing and genuine configured UI refresh remain pending separate acceptance gates. This is not full Task 5, whole-diff PR, merge/main or human acceptance. No product edits, commit, push or desktop automation by reviewer.
