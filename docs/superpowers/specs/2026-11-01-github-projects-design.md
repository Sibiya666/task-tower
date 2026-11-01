# GitHub-backed project workspace

Approved direction: every project owns its repository, Issues and GitHub Project. Task Tower's repository contains only the product's own work. An installation-owned configuration connects independent projects; it is ignored by Git and can optionally live in a separate private configuration repository.

## Data and ownership

Use Python 3.11+ and the standard library. Project connections have stable IDs, repository owner/name, optional GitHub Project URL, local checkout and runner label. No credentials in configuration. Resolve existing credentials at runtime. Reject duplicate IDs/repositories and invalid URLs/paths. Repository plus Issue number is the globally unique task identity.

Issues are authoritative for ideas/tasks and their remote lifecycle. Task Tower metadata is an explicit versioned JSON block in the issue body; preserve user prose. Normal issues remain readable. Labels are views, never locks. Specs/research/results stay Markdown in the owning repository. Do not silently migrate or overwrite existing local cards. Explicit idempotent import retains legacy IDs and evidence, marks unverifiable completion needs_input, and never equates closed Issue with accepted work.

## Books

Aggregate connected repositories into ideas, tasks and library. Exclude PRs from issue pages. Follow pagination with bounds and report partial/unavailable projects visibly. Every entry retains project and source URL. Render three entries per page with project/book filters. Provide a usable CLI and standalone escaped HTML view, with no embedded credentials or inline untrusted HTML. Library entries link repository Markdown files at the fetched commit. Never show stale data as current.

## Distributed execution

GitHub Actions is the durable server queue, self-hosted runners execute project agents. A trusted workflow_dispatch workflow in each project serializes the same Issue with concurrency, does not cancel running work, and routes a fixed project runner label. Different Issues/projects may execute concurrently. Refresh authoritative Issue state before execution; completed work is skipped. An interrupted running attempt needs explicit recovery, never silent duplicate execution. Issue assignment is not an atomic lock. Do not execute arbitrary commands supplied by issue text. Harness commands come from trusted local configuration and existing bootstrap/reviewer code. Keep credentials out of subprocess model environments where possible.

Postmerge acceptance must verify the exact merge commit belongs to main, required CI and independent acceptance before publishing done. Failed/rejected/unavailable evidence cannot close a task. Remote publication failures remain retryable without rerunning a successfully persisted review. Existing local worker remains an explicit legacy mode until remote mode is configured. No claim that another physical machine is registered without evidence.

## Acceptance

Test two project namespaces with equal issue numbers, invalid/duplicate connections, paginated issue/tree data, source failure isolation, HTML injection, idempotent import, duplicate dispatch/recovery, non-main commit/rejected acceptance and publication retries. Document per-project workflow installation, runner registration and local configuration. Keep overlay untouched. Independent spec/code/test acceptance is required; project completion requires main plus postmerge acceptance.

## Clarified implementation and trust contract

Each project owns its GitHub Project. Installation may reference a pre-existing board by node ID and explicit status-field/value mapping; board creation is outside this milestone. An unconfigured board is visibly not configured. A configured board must receive actual Issue membership and mapped lifecycle status idempotently through GraphQL; a URL alone is not integration. Permission/scope and mapping failures remain visible per project, without inventing account permissions or dropping unrelated projects.

Actions serialization is a scheduling boundary, not the sole durable record. Persist pending intent and attempt ownership in GitHub, identify attempts by repository/Issue/run identity, coalesce duplicate dispatches explicitly, and reconcile canceled or unknown dispatch outcomes. Pending replacement and finite queue overflow must not lose authoritative work intent. All remote consumers use the same trusted Issue serialization boundary. Authorized explicit recovery verifies the old attempt is no longer active before replacement.

Persist accepted review and pending publication remotely so another runner can resume publication without repeating a successfully persisted model review. Bind evidence to repository, Issue, attempt, exact candidate/merge SHA, independent reviewer identity, trusted policy version, required check names/source and decision. Issue prose and editable lifecycle metadata cannot supply acceptance authority. Failed, missing, stale, mismatched or forged evidence fails closed. Preserve concurrent user prose through conflict-aware publication/reconciliation.

Load workflow/bootstrap and commands from a trusted default-branch or pinned source, validate Issue numbers, reject untrusted workflow refs and never interpolate Issue commands into a shell. Restrict dispatch/recovery to trusted project operators and runners. Keep credentials out of model environments where possible; inherited credential stores remain a host trust boundary, and worktrees are not credential/process sandboxes.

Preserve Superpowers stage gates and accepted input versions. Per-Issue concurrency does not replace the architecture's repository merge barrier: subsequent automated merges wait for prior postmerge acceptance, while independent projects proceed. This milestone may consume independently produced merge evidence without implementing merge automation; state that limitation explicitly, without implying the barrier is implemented.

Acceptance additionally covers configured Project membership/status projection and visible permission failures; active plus multiple pending deliveries, canceled/unknown dispatch reconciliation; runner-B publication of runner-A review without another model run; forged/wrong-SHA/omitted-check evidence; concurrent prose updates; untrusted workflow refs and unauthorized recovery; and retained stage/merge boundaries. Read-only GitHub smoke does not prove installed workflows, end-to-end execution or a second physical runner.
