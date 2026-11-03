# Bounded postmerge fetch recovery

Goal: let the existing postmerge worker receive fresh main even when Git's HTTPS helper finishes after ten seconds. The observed successful fetch took 11.437 seconds; refs arrived in under one second, HTTPS teardown consumed the tail, and maintenance took only 0.062 seconds.

Scope: grant only the worker's exact `git fetch origin main` a fixed 60-second deadline. Keep other Git calls at ten seconds, origin validation, fresh remote fetch on every cycle, exact-commit ancestry, all three platforms from the same workflow attempt, independent reviewer, evidence binding and publisher-driven closure unchanged. No retries inside a fetch, credential changes, manual Issue closure, journal edits or fabricated results.

Operational recovery: after independent review and tests, a private launcher may load the immutable main release and supply the existing Worker(refresh=...) dependency with the same origin validation and a real bounded 60-second fetch. This launcher changes only the host receipt step; the independent reviewer still checks out and reviews exact main, and the publisher revalidates the genuine source. Stop the idle old worker under journal lock before launch. Preserve logs and receipts. Record the recovery source hashes and limitation; do not claim the main product already contains the timeout fix.

Product fix: add keyword-only `timeout=10` to tasks._git; Worker._refresh passes timeout=60 only for fetch. Document the fixed bound in worker instructions. Deliver a reviewed PR after the prior main cycle completes; do not silently alter a deployed immutable release.

- [ ] Independent specification/operational recovery review.
- [ ] RED tests for exact fetch budget, unchanged default, timeout/nonzero rejection, and origin rejection before fetch.
- [ ] Implement minimal timeout override and run focused regression suite.
- [ ] Independent development/test review and recovery launcher review.
- [ ] Run genuine recovery cycle; verify independent exact-main acceptance and automatic Issue16/Project closure.
- [ ] Commit/push product fix, exact-head/base independent PR review and green CI; merge and verify main.
- [ ] Re-audit accepted main APIs and resume next authorized Windows tasks; POSIX/Claude remain deferred.
