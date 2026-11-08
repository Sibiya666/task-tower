# Bounded checkpoint cleanup

Authorized bug: `tt-azn` (2026-11-08). Preserve checks, timeouts and effect fences.

## Evidence and scope

The retained local watch failure omitted its reason and publication action.
Isolated checks and the original 743-test prefix passed. Its historical cause
cannot be identified uniquely from that receipt.

A separate native Python 3.11 Windows experiment reproduced a matching path:
a read handle without delete sharing on the private Git index caused
`PermissionError` / Win32 error 32 during temporary-directory cleanup. The final
commit was already recorded as completed, but the action returned
`needs_input/environment_unavailable`. The control returned `ready`. Three
verdicts remained intact; neither case performed remote publication.

Fix this confirmed cleanup path and retain useful diagnostics in the existing
watch assertion. Do not claim that a passing retry proves historical causality.

## Approach

Use the existing temporary-directory cleanup, with a bounded additional attempt
only for Windows sharing violation 32. Require the existing host guard, so its
original authority, cancellation and absolute task-deadline checks still apply.
Use a five-second retry horizon: no additional cleanup attempt starts after
it, including time consumed by the guard. The existing guard and supervisor
remain authoritative for task/operation deadlines; no configured task, role,
Git, journal, process or shutdown timeout is extended.

Before each additional attempt, verify the original directory's absolute parent,
device/inode identity, directory type and safe ancestry. A missing directory is
already cleaned; a replacement or reparse point must be refused. Persistent
sharing violations, other errors and guard failures still propagate. Cleanup
must actually finish before normal continuation; no best-effort success.

The executor chooses this limited retry over deferring cleanup to another
controller action, which would add durable cleanup state. Do not use
`ignore_cleanup_errors`, retry Git publication, alter an observed effect, or
replay an unresolved effect.

## Verification

First add a native regression: hold the real index handle after final-commit
completion and release it only after the first actual cleanup sharing error.
Original code must return `needs_input`; the fix must clean the directory and
return `ready` with exactly one final commit and no remote write.

Cover persistent locks, other permission errors, changed directory identity,
guard/deadline refusal and preservation of an exception from the body. Reuse
the bounded `HostObservation` message around the original publication asserts.
Keep every original assertion and timeout. Require genuine full runtime PR CI,
independent exact-head/base review/status, protected merge, fresh 60/10-second
main receipt and independent exact-main matrix/event acceptance before closure.
No UI acceptance, settings, ACL/auth changes, installs or old workers are implied.
