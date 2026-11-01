# Continuous and parallel development process

This policy applies after the user authorizes a bounded project backlog and its integration rules. Keep that authorization, connected repositories and budgets in installation-owned private configuration. Cloning Task Tower does not grant permission to execute arbitrary Issues or merge other projects.

The coordinator continuously selects ready authorized work. It starts up to two independent Issues by default and fills a free slot without a new chat prompt. Readiness requires verified dependencies and the project's authority policy. A task blocked on external input remains visible while unrelated ready work continues. Routine implementation choices and review fixes are handled within the authorized scope.

Each Issue owns a branch, isolated worktree, run identity, specification, plan and acceptance evidence. Executors and acceptors are distinct instances. Stable stage inputs are accepted before the next stage; source changes invalidate affected acceptance. Use canonical UTF-8/LF hashes and keep mutable task-card state out of self-referential source manifests. Unknown external outcomes are reconciled rather than replayed blindly.

## Parallel work and integration

Two Issues may run concurrently when their behavior and data contracts are independent. Record component ownership in their plans. Shared CLI wiring and documentation can be reconciled by the coordinator; coupled changes to a common contract wait or are grouped into one task. Separate worktrees prevent filesystem collisions but are not security or credential sandboxes.

Specification, implementation, testing, independent stage acceptance and PR checks may proceed in parallel across Issues. Only one merge and its main acceptance cycle may be active per repository. After main changes, update the waiting branch, resolve conflicts, rerun applicable CI and obtain a fresh PR verdict bound to its actual head and base. Green checks or a stale approval never bypass this gate.

Completion requires the intended result in main, successful exact-main CI, independent postmerge acceptance and verified GitHub Issue closure. Then update its Project/books projection and automatically choose the next eligible work. Large features remain parent Issues with sub-issues; milestones remain implementation stages rather than execution slots.

## Persistent runtime contract and current capability

The target runtime is a durable queue, deterministic scheduler and bounded worker pool. Scheduling must not depend on keeping an LLM chat alive. One-time project policy defines scope, permitted actions, budgets and the parallel limit. Claims and stage transitions are durable; restart, repeated delivery and multiple workers cannot silently duplicate execution. Ownership across installations requires distributed fencing, not a copied local SQLite journal. Conflicting or uncertain work pauses visibly rather than expiring into a second executor.

Issue #16 owns the stage controller and automatic transitions; #18 owns groups, capacity/conflict scheduling and automatic slot refill; #19 owns verified cross-machine ownership. The executor (#15), PR intake/merge (#17) and guards (#25) supply their respective parts. These milestones are required before claiming unattended parallel development.

Currently the active agent chat coordinates parallel project work under explicit authorization. The shipped dispatcher reads ready Issues and delivers identities through trusted adapters; its eight-submit/eight-lookup budgets are delivery limits, not a pool of eight developers. Its foreground loop does not itself implement development execution or automatic stage orchestration. README and setup guides must keep these boundaries current as each milestone lands.

## Escalation and continued work

Ask for human input only when an actual decision or action falls outside the saved authorization, such as destructive work, irreversible migration, new credential/ACL scope or an unresolved product choice that changes the goal. Preserve the concrete reviewable result and blocker. Continue other independent authorized work while the question is pending. Do not stop merely because one Issue, plan step or review cycle completed, and do not repeatedly ask whether to continue.
