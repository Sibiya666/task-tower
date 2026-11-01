# TT-BOOKS-UI-001 Task 2 independent review

Verdict: **ACCEPTED**. No blocking spec, code-quality or security findings. Reviewer `books_bridge_review` is distinct from implementer. Date: 2026-11-01. Review covers the full actual tracked diff and complete new files of the six owned sources below, frozen at source HEAD `ee7bd4a131429cb121f0320804bfc3d58bf615a4`. This is Task 2 acceptance only, not native UI, PR/head/base, main, or Issue acceptance.

Read repository AGENTS, complete accepted design, applicable implementation plan/common interface, current bottom progressive specification binding, and accepted Task 1 projection contract. Reviewed helper public filtering and configuration isolation; strict UTF-8 NDJSON envelope, sequencing/finality/provenance/unknown entry fields; bounded stream/frame/entry counts; asynchronous single-flight generation ownership and late-output discard; timeout/close kill and reap; bounded-memory stderr discard; stale retained data and prior Done invalidation; and final-ready success only after EOF plus correct exit. Terminal frames are withheld until EOF so an after-final frame cannot publish terminal success. Task 1 owns nested public projection sanitization; helper excludes unknown top-level entry fields and never serializes configuration or raw exceptions.

Reviewed exact native document/action schema and 16 KiB limit, immutable trusted configuration allowlist, HTTPS GitHub source validation, shell-free fixed helper invocation and Windows argument quoting. Existing composition, collector delivery, monitor/input/activity code and legacy actions remain intact; native navigation becomes exact index-only. PowerShell launcher retains UTF-8 BOM. No product source edits, commits or GitHub writes were performed by reviewer.

## Fresh verification

- Supplied Python runtime: `-m unittest tests.test_overlay_books -v`: **7 passed**, exit 0 (0.113 s). Includes real aggregate blocked-verifier synchronization, public/private filtering, malformed config, byte/entry bounds and final-frame capacity.
- `node --test overlay/test-books-host.cjs`: **2 passed**, exit 0 (6.339 s). Fresh Windows PowerShell 5.1 compilation and actual Python helper execution cover exact configured sources/messages, private config fail-closed and immutable allowlist, Unicode/spaces/quotes/backslash argument roundtrip, pre-exit identity/library delivery, single flight, timeout retention, stale proof invalidation, no late publication, malformed/invalid UTF-8/missing-final/nonmonotonic/after-final/provenance/private-field/entry/frame/total limits, and actual owned-process termination on close.
- Independent compiled boundary probes using Windows PowerShell 5.1 additionally rejected decoded NUL/question mark, invalid percent escape, empty Markdown path segment, escaped duplicate action keys and duplicate URL keys: **passed**, exit 0. Probe setup initially used PowerShell Core (framework reference unavailable), then encountered command quoting/execution-policy/array-constructor setup errors; corrected the probe harness and reran under `powershell.exe -NoProfile -ExecutionPolicy Bypass -File <temporary-probe.ps1>`. These were reviewer harness errors, not product failures.
- Fresh canonical UTF-8/LF hashes and launcher BOM inspected. Full CLI/overlay integration suite was not rerun by this reviewer; coordinator owns that gate.

Compiled process-boundary tests do **not** exercise actual composition WebView interaction, focus, screenshots or native book UI. Those remain mandatory subsequent Task 4/5 evidence.

## Canonical source binding

Hashes normalize UTF-8 BOM away and CRLF to LF, matching other stage bindings.

| File | SHA-256 |
| --- | --- |
| `task_tower/overlay_books.py` | `50806c9fceef4a3d340036f0846cb87cf76ef9fc7ad274111ee867fd312f382d` |
| `tests/test_overlay_books.py` | `d23b775620ff132156c09fa61d56bd73ea555861abce31931e74d565582b5e0d` |
| `overlay/BooksBridge.cs` | `0909ac2319e26b4befbb468181267c16ef5c40a0e0e7650596e4a713f6b5728d` |
| `overlay/test-books-host.cjs` | `a77453e715b9975d3e2361804f4b473f8783644eeee0c433a8ce20b05c04db73` |
| `overlay/TowerHost.cs` | `d1df96e557d0646fd7210b96c913a70fac093c75c6fe74e791d8f973897a56cc` |
| `overlay/run-html-overlay.ps1` | `32b59871334595b11099b531c3baef5ca818203e74c3e2013d90fd853670dc4e` |
