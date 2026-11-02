# Pending migration and unavailable library source — author fix freeze

2026-11-02, fixer `/root/pr_reviewer_review`, following coordinator's explicit narrow fix authorization. This is author evidence, not independent acceptance. Previous rejected PR/stage bindings remain historical; Root owns the card/status and fresh PR acceptance. No commits/pushes.

## Reproduced defect and correction

The newly supported unavailable library source=null could compare equal to a legitimate pending legacy migration's issue_url=null. The aggregate's old source-only match then attempted issues[None] and crashed the entire report. New mixed real aggregate regression reproduced exact `KeyError: None` at books.py's relationship lookup before the fix.

Only migration matching changed. Require a positive integer migration Issue number, its exact non-null canonical repository Issue URL, and an entry in Tasks/Ideas with the same configured project/repository, number, qualified identity and source. A library row can never satisfy that binding. Pending/stale rows with no Issue remain explicit fixed pending/stale diagnostics; they are not silently dropped or attached to unrelated artifacts. Genuine current migration provenance still attaches to its canonical Issue. Registry/original card bytes, lifecycle, completion verification, URL policy, native code and HTML rendering remain unchanged.

The regression uses the actual aggregate→library/public projection and HTML snapshot with an unsupported-percent library source=null, an ordinary library sibling, pending and stale null-URL migration outputs and a current canonical Issue migration. It checks all three entries survive, unavailable source stays inert, both pending/stale diagnostics remain, only the Issue carries current migration provenance, public state is partial, and HTML never creates a None/encoded-dangerous source launch. Read-only audit confirmed render_html already maps non-string sources to `#`; no HTML change was needed.

## Fresh checks

Absolute Python `C:/Users/sibiya666/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe`:

```text
python.exe -m unittest tests.test_book_projection tests.test_book_library tests.test_overlay_books tests.test_publication_books -q
47 tests in 0.114s, OK, exit0

python.exe -m unittest discover -s tests -p test_capture_migration.py -q
20 tests in 3.249s, OK, exit0

# overlay/
node --test test-books-host.cjs test-books-browser.cjs test-books-policy.cjs
29 passed, 0 failed/skipped, 15111.5536ms, exit0
```

The initial combined module-form migration command had three legacy sibling-import errors because those tests expect discovery's tests/ import context; rerunning the unchanged tests with their supported discovery form passed. Those harness errors were not treated as production failures or hidden by assertions/skips. Scoped diff-check returned0. No complete new CLI/three-OS CI/native smoke or stage acceptance is claimed for this small Python-only delta; current exact-head CI and fresh independent acceptance remain required.

## Frozen files

| File | Raw SHA-256 | Canonical UTF-8-sig/LF SHA-256 |
| --- | --- | --- |
| task_tower/books.py | `2c6aa9014ab712f5e515e6fa8ac19aa9ded3e2ee352d8322e3212a27379b7793` | `bc18f88c54aa86c11b0840715b6b077531090002eacea75ba57fe716bb89a28a` |
| tests/test_book_projection.py | `9fde760b86fde5506547709a1a5c0f5415d5b2d4875e99e2c45ad7c19e85750e` | same |

No other product files were edited by this fix; card/evidence changes owned by coordinator are outside this freeze.
