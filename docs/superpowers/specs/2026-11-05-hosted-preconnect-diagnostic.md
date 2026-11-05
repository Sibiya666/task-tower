# Bounded hosted Windows investigation of tt-qrk.4

The user explicitly authorizes one bounded hosted Windows CI diagnostic experiment and a justified fix on2026-11-05, preserving all checks and timeouts. This resumes the external-evidence blocker; it does not authorize new conveyor features, account changes or other platforms.

## Known boundary and hypothesis

Actual earlier CI traces reach `_Host.cancelled` -> `PipelineJournal.status` -> `_db` -> `_wait_seconds` before `sqlite3.connect`. The original one-second callback operation budget expired. Cleanup succeeded. The source of preconnection wall time was not recorded. Shorter test temporary roots were a validated workload mitigation, not a proven fix.

One credible workload hypothesis is duplicate ancestry validation: `_safe()` calls `safe_config_path(path)` immediately before `_private_stat(path)`, which calls it again before stat. There is no resource use between those checks. Do not change production code until hosted evidence and deterministic regressions justify a specific correction. Retain validation immediately before resource use and all security predicates.

## Diagnostic delivery

Add a standard-library, test-only runner under tools and focused unit tests. One Windows push diagnostic job, limited to the exact owned diagnostic branch, gets a five-minute job budget and uses the existing contained process supervisor with a240-second child execution budget and actual EOF/cleanup proof. Research can run before opening a PR, avoiding an unrelated duplicate full-suite run. This is not production acceptance or a workflow/code CI waiver: the final fix PR still requires complete ordinary PR/main gates. Run exactly one fixed existing synthetic native WatchTests case, preserving its assertions and internal deadlines. No real project claims, models, task database, installed private config or external HTTP.

Install observation before host creation. Correlate callback records by existing owner UUID and callback sequence. Measure original wall/thread/process CPU deltas, `_safe()` durations, lstat count/cumulative/max timings, original operation-budget remaining at phase boundaries, and the preconnect boundary. Preserve original functions, returns, exceptions and clocks. Add no journal reads, renewed budgets, ownership, cleanup control or locks held across original calls. Attribute outside-safe preconnect work too.

Bound scalar-only records and report bytes, with omission counters. Never serialize paths, exception prose, source, locals, environment, database contents or task bodies. Do not upload raw native stdout/stderr. Only bounded sanitized reports and process facts may be artifacts. Missing reports, skips, failures, timeouts or unconfirmed cleanup cannot become diagnostic success. Ordinary full-matrix CI remains required separately.

The initial experiment runs once; there is no repeat-until-green loop. One later changed-head diagnostic may verify a justified fix. A relevant failure not reproducing must be stated honestly. Wall minus thread CPU does not uniquely identify blocked I/O versus descheduling/GIL contention; process CPU adds context, not definitive causation.

## Correction and acceptance

Require a concrete data-backed cause and meaningful failing regression before the minimum correction. Preserve the one-second callback guard, shutdown/native test budgets, fail-closed outcome, security predicates, identity pins, checkout exclusion, collision checks and temporary sidecar semantics. Do not replace a tight guard with retry, skipping or cached authority.

For any duplicate-work correction, prove rejection of unsafe leaf/ancestor symlinks or junctions including disappearing unsafe observations, hardlinked/nonregular databases and unsafe sidecars; preserve legitimate disappearing sidecars, forbidden collisions, pins and deadline exhaustion. A workload-count test supplements these security regressions, never replaces them.

Independent diagnostic/design and development review, fresh whole actual diff approval at exact head/base, genuine GitHub agent context, all current CI, expected-head merge, independent exact-main source and actual postmerge artifacts precede canonical Beads closure. Keep previous failure history and predecessor evidence intact. Update README/AGENTS with the final justified scope and result. Do not claim a defect fixed from a lone green run.
