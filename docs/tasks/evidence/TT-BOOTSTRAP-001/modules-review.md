# Independent module review: TT-BOOTSTRAP-001 Tasks 1 and 2

Reviewer: bootstrap_modules_review (independent reviewer instance)
Date: 2026-11-01
Scope: task_tower/harness.py, task_tower/tasks.py, tests/test_harness.py, tests/test_tasks.py.
Basis: AGENTS.md, docs/superpowers/specs/2026-11-01-bootstrap-harness-design.md, docs/superpowers/plans/2026-11-01-bootstrap-harness.md.

## Verdict

Task 1: accepted for this module review. No Important/Critical defect found in the reviewed harness implementation. Task 2: changes required due to the Important defect below. This is not final bootstrap CLI review, postmerge acceptance, or cross-platform CI evidence.

## Important: accepted postmerge state does not validate its commit on load

In task_tower/tasks.py, _read validates accepted records only for reviewer/evidence/hash strings; load_task checks evidence hashes only. Neither checks the accepted postmerge record's commit or its membership in current local main. Consequently task show/load can report done for a malformed card without any postmerge commit, or a once-valid card whose main branch no longer exists. This contradicts the requirement that done requires an explicit commit contained in local main, and bypasses validation at the card's read boundary.

Reproduced using a temporary Git fixture from tests/test_tasks.py:

1. Accept spec/development/test, then accept postmerge against the fixture HEAD on main.
2. Delete stages.postmerge.commit from the saved card, retaining all evidence hashes. load_task returns status done.
3. Restore the commit field and rename main to other. load_task again returns status done.

Observed output:

    Missing postmerge commit read status: done
    No main read status: done

Requested repair: validate the accepted postmerge commit's type/hash, resolve it to a real commit, and recheck main ancestry when loading a card; add regression coverage for missing/invalid commit and vanished or diverged main. Re-review required after repair.

## Verification

Windows, bundled Python at C:/Users/sibiya666/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe:

- python -m unittest discover -s tests -p test_harness.py -v: 9 tests, OK, 1 skipped because symlinks unavailable.
- python -m unittest discover -s tests -p test_tasks.py -v: 9 tests, OK.
- Additional temporary-Git reproduction above confirms the Important finding despite the passing tests.

Static review also covered stale saved skill pins, argv construction without a shell, Windows shim rejection, descriptor snapshots, atomic replacement of hardlinked destinations, stage ordering, self-acceptance, stale evidence, and downstream invalidation. Race-free defense against a concurrently malicious filesystem process was not established. No production files were edited and no commit was made.

## Reviewed SHA-256 versions

- task_tower/harness.py: 1ba7f917051428bb9b81c7e3ec232a5b12143a2218833f80cd84b79659beed5b
- task_tower/tasks.py: 2cf63af2e57ac3418dbae2641808172c33281040035508cfde9b9ee17a825f11
- tests/test_harness.py: 84f7168e0d9efe7d26f162a914f933d6351f0b9b39c905f2e16467bd67261f0f
- tests/test_tasks.py: 2728b8bbdf89f8e443fc8217f2bcffe40f0ef6059fec5d36d6ba4f6f95310bff
