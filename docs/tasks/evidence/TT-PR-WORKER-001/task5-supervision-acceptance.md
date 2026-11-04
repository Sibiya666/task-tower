# Persistent PR host and CLI component acceptance

Independent development reviewer `6d4a0782` and test reviewer `9b8a5095`
approved the bounded candidate against base `160528c`. Exact candidate hashes,
review identities and original nonapprovals are retained in
[reviews](task5-supervision-reviews.json). Actual process/capture receipts are
in [verification](task5-supervision-verification.json).

The fixed contained host holds one original journal owner across controller
ticks. Its parent enforces original task and role deadlines through a bounded,
PID-bound private channel and kills the entire tree on uncertainty. Telemetry
does not grant review, publication or completion authority. Metadata commands
remain available with revoked executable inputs and never initialize missing
state. A one-shot execution retires its owner; another invocation cannot adopt
its unfinished work.

The initial independent development review found an unbounded private reload
after idle and lost returned-process evidence when telemetry cleanup failed.
Two actual fault tests failed before the fixes and passed afterward. The full
main chain exposed inconsistent repository casing in telemetry admission;
only telemetry identity normalization changed, preserving original evidence
bytes and hash schemes. The final 20-test replay passed in 273.703 host seconds,
with unchanged source, complete capture and confirmed process cleanup. It covers
actual Git/process consumers, controlled HTTP, main review and lost-response
comment/closure reconciliation without duplicate writes. Earlier 78-test and
35-test regressions are qualified to their recorded earlier source snapshots.

This is component acceptance, not the installed genuine pipeline pilot or whole
Issue17 acceptance. Source-revision/recovery refinement, final full-suite,
exact-head/base whole-PR acceptance, CI, exact-main independent acceptance and
automatic Issue closure remain required. No live writer attestation, protection
change, service installation or production daemon change occurred.
