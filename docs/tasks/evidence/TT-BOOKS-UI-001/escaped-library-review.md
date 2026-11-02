# Independent escaped Markdown contract correction review

2026-11-02. Reviewer `/root/books_pr_acceptance`, distinct from fixer and prior development/test acceptor. **ACCEPTED for the current ten-file development/source correction only.** No blocking finding remains in this frozen correction. This is not final PR, whole TEST-stage, main/postmerge or automatic Issue-closure acceptance.

## Scope and resolved finding

Read the entire actual ten-file correction over rejected PR head168f5b92789de7ce06ab912c2cad037193771a31, accepted Books design/plan, author freeze/TDD report and prior PR rejection. Original private pr-40-168f5b9-rejected.json/.md remains unchanged. All ten raw/canonical hashes independently match runtime-escaped-library-freeze.json (rawSHAe63ba5279d372f6e4371599ac237e59be737dad464d06abcc7ef3541c3c2b258). Root task-card pending changes are separate.

The original normal/#/?/% compiled-native source and complete-frame probes now accept all four cases. Producer, native opener and browser button admission round-trip one canonical RFC3986 UTF-8 path-segment spelling. Spaces, Unicode/non-BMP and punctuation are explicitly covered. Encoded structural separators, malformed encodings, raw query/fragment, dot traversal, controls/C1 and repeated-decoding ambiguity remain rejected. The external browser is never launched by these probes.

Literal percent-triplet names remain immutable, explicit unavailable library records with source=null and available=false plus a fixed diagnostic, retaining healthy sibling rows. Null sources cannot authorize an open action or task acceptance; compiled native and JS require library plus explicit unavailable, and native additionally enforces configured repository/path/commit identity. Safe-row GitHub library compatibility is retained; a per-call derived filtered-path counter reports rejected control-bearing paths without returning unsafe rows. Counter reset before transport prevents stale diagnostics. The real authenticated transport regression verifies this producer path, not only fake rows.

No TowerHost/keyboard source, navigation/CSP, credentials, host command, completion verifier or task-closure authority changed. TowerHost rawSHAadb87c95d8b13ba9ef0e065243974ca14838d589359ca9e3b914a7b21502765a is unchanged, so narrowly recorded prior human Ctrl+B evidence is retained rather than invented anew.

## Fresh independent verification

- Repository: cached Python3.12 `-m unittest tests.test_book_library tests.test_book_projection tests.test_overlay_books tests.test_github_projects tests.test_github_projects_acceptance tests.test_publication_books -q`:68tests0.663s, OK, exit0.
- overlay/: `node --test test-books-policy.cjs test-books-browser.cjs test-books-host.cjs`:29passed,0failed/skipped,21130.5875ms, exit0. This includes actual Python projection to complete compiled native frame and real Edge UI, inert unsupported records, exact allowed actions and negative URI cases.
- Original independent pr40-path-probe.ps1 and pr40-frame-probe.ps1 against compiled current production BooksBridge: ordinary/#/?/% all source-allowed and complete-frame accepted. The original rejected versions are retained in the prior report; no tests were weakened.
- All ten frozen raw and canonical bindings independently matched before tests; scoped git diff --check exit0.

Author reported456CLI tests174.202s and44Node tests32038.166ms before the final diagnostic seam/assertion; those full runs were not repeated here. Fresh independent68/29 checks cover the final seam. The author reported an initial native pre-Books live-room smoke failure and later serialized unchanged-source native smoke exit0; neither is claimed as a new independent native run by this reviewer. The original failure and uncertainty remain preserved in escaped-library-fix.md.

Current remote CI has not yet run on this uncommitted correction. TEST stage remains PENDING until current source is committed and all required current CI succeeds. Final PR head/base acceptance must be refreshed after card/evidence finalization; this source acceptance does not change the rejected PR status.

## Exact current bindings

Canonical text hashes use UTF-8-sig decode with CRLF/CR→LF; PNG hashes are raw. Complete34-path product/test/doc manifest is `36639be437031bc366bbaabc44a5d59b5f67bc9137d1d6a3527c0710e6565613`. All24 paths outside the ten-file correction remain identical to previously accepted manifeste803c1b032406c8fac7d509093a41c944304c20fb26cef733596ef6fb97f5218.

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

No product edit, commit, push, GitHub status/comment, merge or desktop automation by this reviewer. Only requested public review evidence and append-only stage revalidation were written.
