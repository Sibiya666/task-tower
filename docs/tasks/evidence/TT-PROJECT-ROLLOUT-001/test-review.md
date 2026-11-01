# Independent test acceptance — TT-PROJECT-ROLLOUT-001

Date: 2026-11-01. Reviewer: onboarding_test_acceptance, distinct from implementer and development reviewer.
Decision: ACCEPTED for the file hashes below; no unresolved test blocker.
Baseline: 4544611ac81294cb6b7dcf85b7afab3397496a54.

Read repository AGENTS, architecture, onboarding specification/plan and current production/test changes. Applied verification-before-completion. No production edits or remote writes were made by this reviewer.

## Definitive verification

After the implementer's explicit final-source-stable notice, ran from the repository root:

```powershell
& 'C:/Users/sibiya666/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -m unittest discover -s tests -v
```

Result: exit 0; **255 tests in 71.834 seconds, OK (skipped=2)**. SHA-256 inventory of every Python file under task_tower/ and tests/ was captured before the definitive run and checked afterwards: zero changed inputs. Earlier overlapping runs are excluded from this acceptance; an initial mixed-source run observed the two new uncertainty regressions fail before their implementation was imported.

Skipped existing Windows tests: test_harness.HarnessTests.test_refuses_symlink_state_directory (symlinks unavailable) and test_postmerge_journal.JournalTests.test_rejects_symlinked_database_parent (symlink creation unavailable).

## Coverage assessed

- Project-first preflight blocks Issue POST without a configured writable linked board; partial GraphQL errors, insufficient access, wrong owner, ambiguity and incomplete discovery fail closed.
- Fresh setup and repeated setup preserve existing options and IDs, unrelated connections and trusted publishers. Config conflicts and competing writers preserve the newer file. Unsafe reparse attributes are rejected before API calls; journal hardlinks and foreign SQLite databases remain untouched.
- Unknown Project and Issue POST tests exercise a second invocation/new store with empty discovery: exactly one create across both attempts. Subsequent unique remote visibility reconciles the same resource. Local journal failure after Issue success yields visible retained Issue identity and a failed creation_journal stage.
- Import recognizes existing task_id/legacy_id identities, reuses Issue 24 with zero Issue POSTs, blocks duplicate/conflicting identities and incomplete enumeration, repairs partial membership without duplicating, and preserves original body/evidence. Existing verified done is retained; unverified done stays denied.
- Independently executed an additional in-memory fixture probe after source stability: reimport an old open card against each of in_progress, awaiting_merge, awaiting_postmerge, postmerge_review, postmerge_failed and needs_input on existing Issue 24. Asserted project_sync.issue_status equals the authoritative existing state and Issue POST count is zero for all six; passed. This complements the persisted suite's body-preservation and done-trust assertions.
- Bootstrap tests verify connection setup precedes configuration/launch, denied setup prevents both, trusted arguments pass without a shell, partial flags fail, and dry-run does not connect/write private configuration or persist harness state. Existing subprocess bootstrap tests cover local-only operation and Unicode/spaced paths. New fixtures resolve temporary roots canonically, avoiding macOS /var versus /private/var identity mismatches.

## Limits

This is Windows local standard-library/fake-transport verification. It does not attest live GitHub mutations or the actual macOS/Linux runners. Real symlink/junction behavior beyond the simulated reparse test needs available platform CI; the repository Portable CLI workflow targets all three operating systems. No distributed cross-host creation guarantee is claimed: durable journals protect their retained local identity store, and setup still requires cross-host serialization. No overlay/native UI changes were in scope. PR head/base acceptance, remote CI, merge/main/postmerge evidence and Issue closure remain separate gates.

## Accepted SHA-256 inputs

| File | SHA-256 |
| --- | --- |
| `task_tower/__main__.py` | `19597381bf7fa352ab6e4e9a7cf3a1c247815334374b5ee4a1339398a0c65ff4` |
| `task_tower/books.py` | `d5e1a55abfa281c4628464f102c16377276681a8a0394ce9499f9a1efc76fab9` |
| `task_tower/bootstrap.py` | `8881457b237dc5b31e83fd97b6115d3e33a5b489844e9f1d78250bf607193dc1` |
| `task_tower/creation_journal.py` | `b2fc2f68151f2d63415a727914fe17ec123d4ad64f428eb62274576db1975f51` |
| `task_tower/github_tasks.py` | `a177a83b16c1aa2e10f7cd85d5a31b379c597506cf6a4c8bc45cc6c236979a1e` |
| `task_tower/project_connections.py` | `41d4efcf25021e1147ebfd22d32c5541f628f8991d0c59fe11e45118db7520c9` |
| `task_tower/project_onboarding.py` | `65dcbdb110a5f8069d3efdc3fc961b0d34013fd3563b189085272d3d9e048f38` |
| `tests/test_bootstrap_connections.py` | `d2949f776066bfb27ece77f7029edbf7f82a61ba5f2c6277cd2a7ae67ec1bd59` |
| `tests/test_project_onboarding.py` | `306b8219fd68381c034c7219e40dfddaa1b76eb04d06b43da3c7f59c65a35e61` |
| `tests/test_github_projects.py` | `00664d368500ceeb4a7df3147ccbe2b372957f3fab21f8ab4456a61cdfc02a2e` |
| `tests/test_github_projects_acceptance.py` | `158d46f0483ef4f0dac34f73eb6a0b1bace1b0b1045f5cbe7505a628bf24753e` |
