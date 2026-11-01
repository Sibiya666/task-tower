# Independent publication specification review

Scope: the new publication design and implementation plan, with read-only inspection of existing lifecycle/journal interfaces. No implementation review, tests, remote writes, commits or rollout. Existing untracked implementation test changes were left untouched.

Result: accepted for implementation following documentation amendments. No remaining specification blocker. This is not code acceptance or proof Issue 9 closed.

Resolved concrete gaps:
- Shared cross-mode lifecycle ordering for publisher and books, including newer non-done attempts and old approvals reposted later.
- Persisted canonical receipt payload, accepted-input identity and evidence manifest; distinguished editable comments from durable local acceptance.
- Actual API author checks on new and recovered comments, ambiguity rejection and bounded pagination failure.
- Final eligibility checks and uncertain close reconciliation, with explicit remaining GitHub read/PATCH race.
- Plan cases for these conditions and expired leases/stale owners.

Trust boundary: explicit installed trusted publisher credential holders may attest local independent acceptance. No physical runner or cryptographic execution attestation required. Actions artifact mode remains distinct. Retry must not invoke models or rewrite acceptance history.

Validation: reread design/plan against requested installed watcher flow and existing project_worker/postmerge_journal interfaces. Implementation tests and real installed watcher pilot remain subsequent mandatory work.
