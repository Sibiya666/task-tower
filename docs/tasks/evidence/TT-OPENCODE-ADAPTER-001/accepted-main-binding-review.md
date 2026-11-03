# Independent accepted-main downstream binding review

Reviewer: /root/fetch_timeout_diagnosis

Verdict: ACCEPT the changed specification/plan bindings below for Issue18 Task3A and Issue21 Task1 under their existing R3/R4 requirements. This is a fresh content-bound specification acceptance of the dated ABI binding, not implementation/test/native/PR acceptance or permission to broaden either plan.

## Exact reviewed input hashes

| Document | Raw SHA256 | Canonical UTF-8/LF SHA256 |
| --- | --- | --- |
| task-tower-capture/docs/superpowers/specs/2026-11-02-agent-groups-design.md | 1a4be208278e320ca34380ce01fec8fa00b952a013c7e9a1bc14665c3d7f59ff | fc5b3c8e47a9b61a8b44c795faba1bd01059fa91f41cef0300aad0d75a10330c |
| task-tower-capture/docs/superpowers/plans/2026-11-02-agent-groups.md | 6cb81ca4b2b3359cb4d40323d19888b463a679e6e6196c786e24db6970cfcb6f | 6d2b7071f95437de55817755b98c911ebd42337d910fdf4535bb02922043e2f0 |
| task-tower-opencode/docs/superpowers/plans/2026-11-02-opencode-adapter.md | 0397ce05b34a3bb5cd64e62864defb1d0e32620c0ef68d5d4a81c6eaf882c33c | 997e940b5100781053a7e8112915ce02576dc929ce29625b7aa5c4200a7a9419 |

Unchanged Issue21 design: task-tower-opencode/docs/superpowers/specs/2026-11-02-opencode-adapter-design.md, raw SHA256 aafe165c23182656f85fe272b8fa2ee0fd03a73627fb7e515bf6fa18cf93c03b.

Accepted-main audit: runtime/accepted-main-487-contract-audit.md, raw SHA256 d5f39f6313f25265f9ff3996be506034b0b70dfa6bdc6a26535853fb78cd4549. Both task-owned evidence copies have exactly this same raw hash, and all three relative Markdown links resolve to their intended task-owned copy.

## Comparison method and findings

Read all three new dated binding sections and compared them against the actual accepted-main AST/source audit. Removed only each newly inserted 2026-11-03 Accepted binding block in memory, normalized line endings, and recomputed the remainder's hash. The resulting canonical hashes exactly reproduce the original reviewed documents frozen by the audit:

- Issue18 design: 198a1c180e3c019482e2f47175de5bb60bcc6a9c9255de2597e204ee0fc94647.
- Issue18 plan: ccc929d681322a3f9d96f006b14a3eabd541ec010f01d1fdb3eb1812fcaf72e1.
- Issue21 plan: 605528f322857405675780f373036acdfc15ab0c117a655da30c9032d1b3f420.

Thus the prior R3/R4 text, schema proposal, Windows limitations, unknown/replay/resource and qualification requirements remain intact. Existing pending-gate statements are explicitly qualified as historical for the now-accepted M; the new sections retain re-audit after future main changes.

The actual gate is correctly bound to main4875381be68282a7ad77ab7b1c5a3898cbc09304, same-attempt CI41503463955, independent exact-main APPROVE and genuine publisher receipt https://github.com/Sibiya666/task-tower/issues/16#issuecomment-6595253516 with Issue16 closed/native Project Done. PR64/Issue63 is explicitly excluded from this accepted base.

Re-read actual immutable-release PipelineJournal AST: _recover_existing(self) has no identity parameter; _existing_database(self, identity), _pinned_database(self), _assert_existing(self), _db(self, write=False, *, initialize=True), operation_deadline(self, deadline) and constructor keyword defaults match the amended18 plan. The six-table digest/application_id/user_version and shutdown4.8s bound are correct. No public PinnedDatabase or accepted group migration interface is invented. Existing named18 test modules are present on M; test_group_migration is correctly identified as future TDD work.

Issue21 correctly enumerates the real generic/role builders and policy/admission/continuation/worker/role paths. It requires explicit codex/custom closure before common-loader expansion, retains unsupported OpenCode six-role behavior and preserves supported argv. Actual role signature has keyword-only role; effective process runner has only cancel_requested/capture optional keywords, no stdin_spec or scope. WindowsJobProcess has no stdin parameter. All named existing21 test modules and the focused discover filename exist on M. New adapter/discovery modules and future Task2 stdin transport remain future work. Full60 is correctly described as60 instruction files. No CLI probe/install/auth/model or POSIX qualification is granted.

No blocking finding remains. Only this report was written; no source, Git metadata, runtime state, DB, process, credential or native tool was changed during this review.

## Stage receipt and implementation boundary

Root should retain this fresh review as a new hashed specification-stage receipt or append-only acceptance entry for each affected task, binding the document hashes above while preserving all prior R2/R3/R4 verdicts and failures. Replacing an old hash/verdict as if it had reviewed these new bytes would be incorrect. A copied report or appended evidence may be used if the task card points to the actual final evidence hash and the historical input/verdict hashes remain recorded.

After that bookkeeping and actual checkout integration of accepted M, Issue18 may start its already specified Task3A migration TDD and Issue21 may start its already specified Task1 policy/closed-dispatch TDD. This acceptance does not authorize migration of a live user journal for convenience, broad runtime group execution, unqualified native OpenCode, source/admission/backend redirection, POSIX58-62 or deferred Claude20. Independent development/test stages, exact-head/base review, green CI and main acceptance/automatic closure remain mandatory. Later accepted-main changes require an affected-interface re-audit; do not import unaccepted PR64 as current main.
