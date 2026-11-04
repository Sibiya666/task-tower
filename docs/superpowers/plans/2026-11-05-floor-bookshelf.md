# Floor bookshelf implementation plan

> **For agentic workers:** Use superpowers:executing-plans for this single cohesive UI change.

**Goal:** Place three spine-facing books on a wooden shelf in the selected floor; open them as a warm parchment spread with bottom corner navigation.

**Architecture:** Reuse BooksView, BooksPolicy and the existing read-only native bridge. Add an independent shelf module notified by Tower render. Keep current source semantics, filters, details, focus trap and freshness reporting. Three records per spread remain the existing quota; left page contains controls/source health, right page contains records or detail.

**Tech Stack:** Local DOM/CSS, existing WebView2, locally bundled OFL Press Start 2P with Cyrillic.

**Spec:** User-approved chat description (three books, Ideas/Tasks/Project library; beige-yellow parchment, folded lower corners, pixel font), plus existing overlay-books design and local-beads-books spec.

## Global constraints

No source mutations, automatic refresh polling, network in WebView, or changes to real agent activity. Preserve transparency, room drag, source validation and reduced motion.

## Review focus

- Small 300–340px native floor: both page corners reachable; page content scrolls inside the spread.
- Progressive refresh must preserve selected book/project, focused control and pending/stale state.
- Shelf must disappear in overview and remain usable after room rerender.
- Shelf clicks open only the selected book; movement beyond the existing 5px drag threshold moves the window and suppresses opening.
- Cyrillic font loads locally under existing CSP; long external strings remain safe and contained.

## Task 1: Shelf and parchment presentation

Files: overlay/web/books-view.js, books.css, new bookshelf.js, index.html, tower.js, assets/fonts; overlay/test-bookshelf.cjs.

- [x] Add real Edge test for floor-only three-book shelf, opening chosen book, two page regions, page-corner navigation, Escape focus restoration, resize and transparency.
- [x] Run test and observe missing shelf failure; run existing Books tests as baseline.
- [x] Add shelf and render connection; extend open(projectId, book) without changing old invocations.
- [x] Style existing read-only content as two parchment pages; preserve DOM text rendering and safe sources. Add local licensed font and folded navigation corners.
- [ ] Run Books/overlay/full Python checks and native smoke; capture synthetic browser UI evidence, distinctly labelled from real live source evidence.
- [ ] Obtain independent whole-diff review, record actual results, commit and integrate only through current PR/main gates.

## Execution ledger

- 2026-11-05: User approved design through “Продолжай”; implementation stays inline. Existing unrelated canonical checkout edits preserved by using clean linked worktree on origin/main d6a7e3c.
- Ruling: Preserve the existing three-record spread quota and use the left page for controls/health, right for records, rather than double the current quota. No source contract change.
- Ruling: Shelf participates in the existing 5px scene drag handler. Blocking its pointerdown made an established room drag region stop working; the scene's capture handler already suppresses the book click after dragging.

- Independent implementation reviewer found and verified fixes for two project-scope issues; final Books checks15/15. Full product suite and integration remain pending.
