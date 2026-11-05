# Bounded evidence for intermittent Windows test-host failures

Parent Beads bug: `tt-qrk.4`. This is test-fixture observability, not development of the archived conveyor or an established bug fix.

## Observed failures

- PR77 postmerge attempt1: `test_stop_during_validated_cancel_read_remains_bounded` failed its first preparation `ready` precondition with `unknown`, before the measured cancellation test. An unchanged isolated local case and one bounded CI repeat passed; original cause remains unknown.
- Rejected PR79 head2635: `test_public_work_contains_blocked_git_descendant_and_no_replay` reached one accepted verdict instead of three. The unchanged isolated local case passed with complete host capture; no callback exception or shutdown failure was observed.
- PR79 head9bd CI41928888029: `test_real_dispatch_adapter_to_six_roles_and_host_tests` timed out waiting for `ready_for_pr`. The row was `unknown`, reason `owner_dead`, stage `test`, generation7, process_count7. Recovery's `owner_dead` is an observation, not the reason the process stopped.
- PR80 headb4cc CI41935061044, shard2 job126941315118: `test_lost_pr_response_is_unknown_and_restart_never_posts_again` failed the `accepted_publication()` preparation assertion with `unknown`, before intentional lost-response injection. This helper had no observer, so the log supplies no host/shutdown discriminator. No shared cause is established.

Do not assume a shared cause. The separate C:/D: docs-test fixture error is corrected in PR79 and does not explain these observations. Preserve original CI logs/manifests/events and do not run another blind retry.

PR80 head66ca CI41937740286 now records a `ValueError` escaping `cancelled()` during the fourth preparation helper. The runner returned `unknown` after containment, and all nine shutdown proofs were true. The callback duration1.156s does not prove deadline exhaustion; exit1 does not prove an independent child crash. The exact raise site remains unknown.

## Narrow implementation

Create `tests/fixtures/host_observation.py` and `tests/test_host_observation.py`. Change only diagnostic wiring/messages in the named WatchTests/precondition helpers, including `accepted_publication()`. No production pipeline, journal, supervisor, clock, task admission, authority, timeout, test expectation, retry or cleanup-control changes.

`HostObservation(fixture_root)` is a context manager exposing a lazy assertion message and `message(journal=None)` for a failure-only bounded report. It may wrap existing parent-host methods and restore every wrapper on exit. Always call original functions and preserve their return values/exceptions. Never acquire execution ownership, mutate a journal or close/terminate a host itself.

Observe the parent's actual host outcome/parsed result before normal close; original cancellation callback exception type and duration; exact owned run fields already returned by its ordinary validated status read; original stop/budget flags; and original shutdown result. Do not add another database read inside the cancellation deadline. If capturing additional host stderr/result bytes is necessary, limit reads to the known synthetic fixture and apply existing safe-path semantics, bounded bytes and credential redaction; never read configured project databases or arbitrary files.

Normal passing-path observations must be minimal. Prepare reports only when an assertion fails, so adding a message must not eagerly read the journal before every successful assertion. Do not hold an observer storage lock while calling product code, journal methods or filesystem I/O. Hook cleanup must be safe with the fixture's existing threads; restoring observation must not wait for, cancel or convert their results.

## Bounds and privacy

- At most32 host records and16 error records, with explicit omitted counters. Keep only known scalar fields, UUIDs, state/stage/reason, status/exit/PID, timestamps, duration, hashes and cleanup flags.
- No environment, profiles, request/task prose, admission/manifest bodies or raw database dump. Redact GitHub credential values case-insensitively if an exception/result string could contain one. Bound strings before formatting.
- A valid ASCII-escaped JSON failure report is at most16KiB. Prune records and include truncation/omission flags rather than produce invalid truncated JSON or allocate an unbounded message.
- On an already observed exception only, permit bounded traceback locations using fixed allowlisted repository module/function identifiers and numeric source line numbers, never traceback text, source lines, locals, absolute paths or exception messages. Bound traversal and retained locations. Permit at most three explicit cause links, known exception class identifiers and numeric SQLite error codes, correlated with the observed host UUID and callback sequence. Preserve the16-error and16KiB caps, original exception identity and unchanged passing path; do not add hooks or journal reads.
- Do not change the native measured cancellation phase in `owned_role_with_delayed_cancel_read`; observe its initial preparation only. Observe publication preparation only before the blocked-Git portion. The watcher test may carry the observer through its existing precondition wait, with the same180-second limit.
- In `accepted_publication()`, observe only its admission host and existing25-iteration preparation loop. Preserve the forbidden-state assertion, status/history reads, three-verdict return condition, returned run and normal close. Return inside the context so restoration finishes before either caller performs publication actions or sets `lost_post=True`.

## Integration

The initial preparation assertion still requires `ready`. The publication assertion still requires three accepted verdicts. The real-dispatch watcher still requires `ready_for_pr`, six model-role fixture attempts, seven distinct instances and three verdicts. All existing cancellation, no-replay and cleanup assertions stay intact. The observer must reveal failure rather than normalize it.

## Acceptance and non-claims

Meaningful tests inject callback exceptions, absent/failed host outcomes and shutdown-false observations and prove original results/exceptions remain unchanged. Test report caps, credential exclusion and hook restoration. Run the unchanged affected native cases with actual EOF/cleanup evidence, then independent whole-diff head/base review and real full Windows CI/main acceptance for diagnostic delivery.

A diagnostic commit reaching accepted main does not close parent bug `tt-qrk.4`. A captured cause and a justified independently accepted fix, or an explicitly recorded external evidence blocker, are still required. If all runs pass, say that no failure was reproduced; do not claim the original defect fixed, the symptoms unrelated or the system ready unattended.
