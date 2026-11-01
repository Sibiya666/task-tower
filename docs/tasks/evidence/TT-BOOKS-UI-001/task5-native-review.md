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
