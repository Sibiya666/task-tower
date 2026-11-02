# Issue 23 Task 5 native smoke evidence

2026-11-02, base `a60bd1d`. Smoke-only `overlay/TowerHost.cs` SHA-256: `4085e3d5bde01fbe4ac9df1d9db642736904106844495f1b1e921169d9b4f820`.

From `overlay/`: `C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe -NoProfile -ExecutionPolicy Bypass -STA -File overlay.ps1 -SmokeTest`. Existing launcher uses absolute Python `C:/Users/sibiya666/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe`. Final native execution returned exit 0. `runtime/html-host-result.txt`: `PASS: Books native smoke; transparent composition window, clear alpha background, native pin controls, live towers, wide-window layout`.

Actual WPF composition WebView2 received a deterministic public partial fixture through native `PostWebMessageAsJson`. Closed remote state retained pending verification. Malicious-looking description remained literal text without an image node. Synthetic DOM Ctrl+B, Tab/Shift+Tab boundary wrapping, Escape detail-first/dialog-second, invocation focus restoration, Shift+F10 and the actual context Books button passed. These are handler assertions inside real composition, **not physical keyboard, UIA, human interaction or human acceptance**. Coordinator owns actual keyboard acceptance separately.

The production opener rejected a lookalike host. An isolated production BooksBridge with an explicit fixture repository accepted its exact Issue using a recording delegate and rejected a disconnected repository. No allowed source opened an external browser. A separate bridge attempted a deliberately nonexistent Python executable; its real unavailable envelope reached the view. Native compact bounds were unchanged on Books open. Existing pin, alpha, clamp and overview restoration assertions passed.

`CapturePreviewAsync` captured the actual embedded CoreWebView2 surface; no desktop content or image processing:

- [Partial fixture detail, overview](../screenshots/2026-11-02-books-native-fixture-overview.png), SHA-256 `d903d2ba9d65d95ac9458480fb558b483e1c1fc8a6da54336ca00d64d700d7d8`.
- [Helper unavailable, 340×300](../screenshots/2026-11-02-books-native-unavailable-compact.png), SHA-256 `ae1061970092c965affab481bbe5685b7203b8e7fff639f1a71a3263d8585f2a`.

Both images were visually inspected: readable overview detail with internal scrolling; compact modal fits horizontally and scrolls internally. Opaque book surface is intentional; outside alpha was separately asserted. Fixture screenshots do not demonstrate live GitHub data.

An earlier expanded run failed because its test selector clicked the menu Close button; changing the selector to the Books button fixed it and final complete smoke passed. A default-context launch was attempted but is not acceptance evidence. No user app was stopped. No production behavior changed; this does not claim live refresh or Issue completion.
