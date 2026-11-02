# PR40 escaped Markdown source contract — author fix freeze

Fixer `/root/pr_reviewer_review`, 2026-11-02, following coordinator GO after independent PR rejection. This is implementation/TDD evidence, not self-acceptance. Previous PR/stage reports and rejected head remain preserved. Fresh independent whole-diff development/test/PR acceptance and current CI are required before integration. No commits/pushes by fixer; Root owns the task card and status.

## Defect and contract

Actual project_library could emit valid Git Markdown names `docs/a#b.md`, `docs/a?b.md`, `docs/100%.md` with canonical quoted URLs, while native IsAllowedSource refused them and rejected the whole frame, including healthy siblings. Producer/native/browser now use strict single decoding followed by exact RFC3986 UTF-8 per-segment re-encoding. Literal #/?/% plus spaces, Unicode and non-BMP Unicode work through immutable escaped links. .NET Framework EscapeDataString and JavaScript encodeURIComponent leave !'()* unescaped; explicit replacements align them with Python quote(safe='/'). Raw query/fragment, control bytes, C1 controls, colon/backslash, dot segments, encoded separators, malformed UTF-8, noncanonical escaping and repeated decoding remain rejected.

Literal percent-triplet filenames remain visible but inert: immutable path/commit/declared state, available=false, source=null and a fixed unavailable-source diagnostic. Only unavailable library rows permit null source; task/Issue sources and available library sources remain strict. Unavailable declaration state does not become task Done. Unsafe control-bearing paths are rejected, not represented as valid null-source artifacts. The GitHubTasks.library safe-row return contract is unchanged: a fresh derived count of filtered unsafe Markdown paths feeds a fixed summary diagnostic to project_library, preserving healthy rows without returning unsafe URLs. Counter resets at each call, including before transport. docs/github-books.md clarifies this public nullable-source contract.

## Observed RED

- New actual producer regression failed because unsupported percent-triplet filename still had a launch URL rather than null/inert state.
- Compiled native whole-frame regression failed `complete real producer escaped library frame retained` on the actual producer's combined ordinary/escaped rows.
- After producer null handling, real Edge regression failed on the unsupported row because old policy rejected the entire nullable-source frame. Corrected narrow policy admitted unavailable library null sources.
- Authenticated real GitHub tree transport regression failed with errors=[] instead of the fixed filtered-path diagnostic; the derived per-call counter/projection correction turned it green.

An initial Python command was accidentally invoked from overlay/ and failed import; it was rerun from repository root to observe semantic RED. A controlled native helper fixture initially exited0 with a partial terminal frame; this correctly failed the unchanged exit contract. The fixture now returns1 like production. Neither preliminary harness issue is claimed as the product RED, and no production exit validation was relaxed.

## Verification and limits

Absolute Python `C:/Users/sibiya666/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe`.

- Complete CLI `-m unittest discover -s tests -q`:456tests174.202s, OK,4existing skips, exit0. This preceded the final added declaration assertion and bounded GitHub filtered-path diagnostic seam; final focused checks below cover those additions without claiming a repeated full suite.
- Complete documented overlay Node list including Books:44passed,0failed/skipped,32038.166ms, exit0. Actual Python producer→compiled native complete frame→real Edge tests cover ordinary sibling plus #/?/%, RFC3986 punctuation, Cyrillic/space, non-BMP rocket, two inert literal-percent-triplet rows and valid rows after rejected C1 paths. Strict negatives include %2f/%5c/%2e, repeated escapes, raw query/fragment, malformed UTF-8, C0/C1 and null-source misuse.
- Final focused shared Python `-m unittest tests.test_book_library tests.test_book_projection tests.test_overlay_books tests.test_github_projects tests.test_github_projects_acceptance tests.test_publication_books -q`:68tests0.654s, OK, exit0. Includes real authenticated HTTP tree/index transport, derived-count reset, safe-row compatibility and unavailable accepted declaration retaining immutable binding/status=source.
- Actual Windows PowerShell5.1 native composition smoke: first concurrent run failed the existing pre-Books live-project-room assertion. Its referenced own collector snapshot was absent when inspected; resource contention is not proven. One serialized retry after CLI/Node completion returned exit0 with unchanged native source. Original failure is preserved here; no TowerHost assertion was weakened.
- Scoped diff-check of all changed files returned0. No keyboard/TowerHost source, CSP, credentials, general network capability or task completion verifier changed. No new physical-keyboard retest claimed or required for this URL-only change.

Remote CI, fresh independent acceptance and final stage/card rebind remain required. Prior physical Ctrl+B evidence remains scoped to unchanged TowerHost; no full genuine source refresh is invented.

## Exact frozen content

`runtime-escaped-library-freeze.json` raw SHA-256 `e63ba5279d372f6e4371599ac237e59be737dad464d06abcc7ef3541c3c2b258`. Canonical column uses UTF-8-sig decode and CRLF/CR→LF UTF-8 bytes. Root-owned task-card changes are excluded from this author freeze.

| File | Raw SHA-256 | Canonical SHA-256 |
| --- | --- | --- |
| task_tower/book_library.py | `b13d1270761eb79b656ca0fd28963fb38d0752730a4169974f26468888e0f0f6` | `b13d1270761eb79b656ca0fd28963fb38d0752730a4169974f26468888e0f0f6` |
| task_tower/github_tasks.py | `4d3e32bbfd81e1f4c13c6979da449dcfb4ecbc44312fed26e1f2263d59667be2` | `8a1b6a84b7e26f9fb8e8bd7e4cc4faaebcda784bfe103519fa1a07d34f3675a8` |
| overlay/BooksBridge.cs | `78f32ca480fca1bde765f52124458774e4e6003797365be9fa60fb6839a1cf16` | `3e3ac7d1c518a6ff94ff11f1caec65b2cde9a731940c82724433d802567f8bbb` |
| overlay/web/books-policy.js | `e2ad73e72581113fbede8cb91c17fccae6136fa1977b2acfc3b16d060843b27e` | `72ec8b606aaf17c7cdb83642764bd46b4a0a9888142d3261da433e4954d54bbb` |
| overlay/web/books-view.js | `abe1a8090d72e22452f12fe0c4b2a18153c70d46bd63eafbf247d267fe71664e` | `7132348dd3b38d7c52255de1e19f57acf7784f95682739d12a67a809df0fa9e2` |
| overlay/test-books-host.cjs | `743d7996d0fe611ca0f4439bc6bb80c88bc85aaef37965c7af1cb0a5766d09a8` | `9e587cd592591023f3bb5446904896cfe9060393240804935ccc8a4732f88e71` |
| overlay/test-books-browser.cjs | `e3b51edbb0f227841e3d992bf096c7508cf83b53d89d17cc46e2d6b034fcc0c0` | `7554f27c678418f9a36d146f010391a13dd0fec9a5ed37b04087cad56dec5708` |
| tests/books_overlay_fixture.py | `0084fb418064773508105587db82102d6b93ee33bfc467a587c29c89edff83ef` | `17be4790c063aeba6c81afc5b5e9e64b5a4be41338ea19fe25504177ce9e8403` |
| tests/test_book_library.py | `5485384e40b6b1daedfaea56bc0bf8df51fc229e143264ff18cefe3f8cd3c280` | `5485384e40b6b1daedfaea56bc0bf8df51fc229e143264ff18cefe3f8cd3c280` |
| docs/github-books.md | `ccac71be173d44f95b6f42375e8f87f25a090c6c835bbadff034f7dca19326ac` | `781d8cd455e3866355cbb8ae0811650b7440879dce0903f5215dd506116b1ab8` |
