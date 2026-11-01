# Independent development acceptance — TT-DISPATCH-001

Verdict: ACCEPTED. Reviewer: dispatcher_development_acceptance, distinct from the implementers. Reviewed the whole actual dispatcher implementation/documentation diff against base 4dc8e32420e5a9ddfa19852379cf6270ce9702e4 and the accepted dispatcher design/plan. This is development-stage acceptance only; independent test, exact-head/base PR, CI, exact-main postmerge and automatic Issue closure remain separate gates.

Review covered private allowlist/configuration and path aliases; complete same-tick repository identity indexes; metadata aliases, qualified/local dependency forms and fresh verified_done proofs; lifecycle exclusion; per-project failure isolation; durable at-most-one submission across process races/crash/restart; irreversible unknown intent and authorized reconciliation; canonical journal constraints/row validation; managed adapter request/result files; protocol bounds/sanitized reports; readonly dry-run/status; bounded workloads and capability documentation. No Issue-derived commands or GitHub mutation path was introduced. processes.py and windows_job.py are unchanged against the base.

Findings resolved before acceptance: stale open lifecycle with recorded remote attempts; readonly SQLite WAL sidecar creation (WAL is rejected before SQLite opens, preserving all state); corrupted rows and same-column schemas missing required constraints; journal operational exit status; deferred/accepted state visibility; reservation-race lookup-budget bypass; final source outage reporting. No unresolved blocking findings remain in the bound source.

Independent verification on the stable source: Python unittest discover -s tests -v completed 298 tests in 82.498s, OK (2 existing platform skips); the focused dispatcher modules completed 43 tests, all successful. CLI dispatcher --help succeeded. Additional hermetic probes proved twenty ready identities submit in deterministic 8/8/4 ticks; all twenty accepted states remain visible during byte-identical dry-run; twenty unknown intents reconcile eight per tick, cover all twenty across restarted ticks, never submit, expose deferred identities and retain operational failure while unresolved. No production edits, commits, remotes or external application mutations were performed by this reviewer.

Remaining documented limits are intentional: foreground delivery is not development execution; GitHub/private-authorization edits after the final check are non-atomic; lookup read-only behavior is a trusted adapter contract; independent journal copies/machines lack shared deduplication; preserving the journal is mandatory.

Canonical manifest scheme: sha256-utf8-lf-v1. Decode each text file as UTF-8, explicitly normalize CRLF and CR to LF, encode UTF-8, and SHA-256 the resulting bytes. The base binds unchanged files. Mutable task-card and evidence files, including this evidence itself, are excluded to avoid self-reference. The following stable sources were rechecked unchanged after verification:

- AGENTS.md: 5dca4fae766f6c995ef9769b296c2bbdf719e8af8ee60413c6d09024a0f11c7a
- README.md: 2553c2452205e3571dce996fea7b8feb93357fd62d967afccc18a3d8a00a09cd
- docs/roadmap.md: dbc8b14afb80c05ee2cb54400297f14a1f09a2ead62062e5dba09ee7676d7f81
- docs/dispatcher.md: 7d53d308e6ee03918275bb58241ee9b50ff0ce62dcc88a95e74e551a84482208
- docs/superpowers/specs/2026-11-01-issue-dispatcher-design.md: 25650b8545c364d5aa80fa2732e44ea3b6285151e540c9dd0315c6c396d0e36b
- docs/superpowers/plans/2026-11-01-issue-dispatcher.md: fb18a98a61898cd6e0d0c314167e98170783a3d06e06bddaf2ac55faf2538d2c
- task_tower/__main__.py: 1021fdfe68d8f948a9a21685986ae4c1d6523a69dab5d39e4d0a0072f6f1f065
- task_tower/dispatch_selection.py: 1bdf8204ec789a32c89dd6a5b4345fb94b590dfd2c9df8b8ee9b3ead9ce77088
- task_tower/dispatch_delivery.py: 47c11dd30143d5e80a57c4c900198a17c7c29796d8454090576e8318505700e0
- task_tower/dispatcher.py: 4bad20664806c6d42ad2a3f76f472b83c2db3cd04947bce411373036f5ffafb9
- tests/test_dispatch_selection.py: ac8a64e9f54ab13b4b8fb1f4e8662c4aeea1d14e9de92185fbbd7d73fcb66345
- tests/test_dispatch_delivery.py: f363113a265563469a75e1cfb68a5a5a9095d1565d41bde060703e4b99d316ea
- tests/test_dispatcher.py: 3001755ea884ea791cb77602e295807b356399d95942133d7c2b7579ebdd4245
