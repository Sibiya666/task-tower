# Merge-event implementation plan

> **For agentic workers:** Use Superpowers TDD and independent review for implementation.

Goal: server-side merge hook exports checked exact-SHA events, with no false task completion; fix text-evidence portability surfaced by pilot.

Spec: ../specs/2026-11-01-merge-event-design.md.

1. tasks.py/test_tasks.py: RED regressions for CRLF checkout then explicit scheme-dispatched evidence hash. Legacy raw remains strict, unknown scheme rejects. No automatic rehash of old acceptances.
2. merge_events.py/test_merge_events.py: pure build_merge_event(payload, repository, platform, checks, run_id, attempt) -> dict; validate GitHub closed merged main payload and explicit task marker, event metadata and deterministic delivery key. Standalone module CLI reads event file, writes output atomically, no model/network/mutations of task cards.
3. .github/workflows/postmerge.yml: closed/main+merged gate, checkout merge SHA, matrix three OS, run full CLI tests, always export/upload event per platform. Read-only token and bounded timeout.
4. Independent review and full suite. Save failed PR#2 postmerge report, request fresh independent evidence review before migrating its old card. No mark done until checks accepted on actual final main commit. No commit/push without user request.

Limitations: artifacts are ready for future task-manager sync; no local listener, public endpoint, automatic importer or autonomous agent acceptance is claimed in this increment.
