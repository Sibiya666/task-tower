# TT-BOOKS-UI-001 independent specification and plan acceptance

Verdict: **ACCEPTED**. Builder check: **nothing important left**. No blocking author questions. This accepts implementation readiness, not feature implementation or UI acceptance.

Reviewer: fresh independent `books_ui_spec_acceptance` instance, distinct from document author and future implementers. Review date: 2026-11-01. Worktree branch: `feat/books-ui`; checked source/base HEAD: `918554a1e7f6dec10f81a366c1dececa845ff072`.

## Exact accepted documents

Hashes are SHA-256 over each complete document after CRLF/CR normalization to LF, encoded UTF-8 without BOM. No AGENTS, cards, implementation or mutable evidence is included in this acceptance scope.

| Document | SHA-256 |
| --- | --- |
| `docs/superpowers/specs/2026-11-01-overlay-books-design.md` | `5c87604c4178a4f57051adc626444cc91c4dd6e92da5eb6e92da5eb6e063d364206dd2d4d` |
| `docs/superpowers/plans/2026-11-01-overlay-books.md` | `dc446206eb4f30f8c7081d2f47636e125da648d2940fc95fd01a6b1eb338a308` |

Changing either document invalidates this verdict. Implementation and integration acceptance remain separate gates.

## Review basis and findings

Read repository AGENTS, architecture design, both complete documents, the Superpowers builder-check prompt and writing-plans requirements. Inspected current `books.aggregate` and escaped flat HTML, `capture.relationship_projection`, lifecycle/verified receipt source, GitHub library tree projection, connection validation, native host message/launch/placement behavior, existing CSP, world menu and tower handlers, and located current books/capture tests. Fetched the native Issue through the GitHub connector (`Sibiya666/task-tower#23`) and compared its full body, including appended bookshelf criteria. The unavailable local `gh` executable was bypassed using that connector; it is not a task blocker.

The design covers the actual Issue: shared aggregation; at most three records across groups and expanded children; filters/details/blockers/results/history; repository-qualified identity; independent milestone and native parent/sub-issue relationships; completed and unassigned records; explicit Markdown states and immutable versions; visible unknown/stale source state; real Windows and keyboard evidence; minimal transparent UI and unchanged activity invariants.

The builder can implement without inventing a major contract. The envelope, entry shapes, module/function names, error states, numeric limits, freshness threshold, manifest schema and absent/unavailable distinction are pinned. Known public lifecycle evidence can be derived from existing validated receipt/attempt contracts; unknown metadata is expressly excluded. Existing captured provenance, ordinary Issue relationships, migration references, flat CLI/HTML consumers and independent `verified_done` semantics must survive the additive projection. Manifest associations are constrained to materialized configured repositories, with no project discovery. Version availability requires an actual blob at the declared commit, and declared acceptance is visibly distinct from task Done.

Trust boundaries are adequate for implementation: private installation config is not a WebView payload; native allowlisting is derived from trusted configured identity; fixed helper invocation is shell-free; exact document/message schema and URI checks are required; CSP/navigation restrictions remain; external text is inert. Host ownership, attempt identity, deadline, bounded reads, stale retention and close reaping are explicit. Windows argument quoting and malicious URL tests are assigned to native harnesses rather than assumed safe from string matching.

Hierarchy pagination, cycles, filtered/disconnected parents, multi-stage features and loaded versus unknown child counts have explicit rules and tests. Context entry, optional explicit scoped mapping, small room viewport, modal close ordering, focus trapping/restoration and drag exclusion are sufficiently specified. Exact visual details and safe diagnostic wording are routine builder choices under delegated authorization.

Task ownership is implementable: projection/library Task 1 and pure fixture-driven policy Task 3 can proceed independently; bridge Task 2 consumes Task 1; UI Task 4 consumes Tasks 2/3 and serializes shared host integration; Task 5 owns full/native evidence and coordinated documentation. TDD commands and failure expectations are present. Actual Windows composition, keyboard interaction and raw focused screenshot evidence are mandatory; browser/source-contract tests cannot substitute. Failed native prerequisites block UI acceptance. Full tests and independent exact-head/base PR, exact-main postmerge and automatic closure gates remain required.

## Acceptance limits

No implementation tests or native UI checks were run because this stage reviews documents only. This report does not assert source freshness, access to private config, implemented sanitization, task completion, passing CI, merge approval or unattended operation. The planned source allowlist deliberately keeps unsupported/session URLs inert; implementation reviewers must verify that boundary and public evidence projection against actual code, not accept this report as proof.

## Revised progressive contract acceptance (current verdict)

Verdict: **ACCEPTED**. Builder check: **nothing important left**. This section supersedes the earlier document binding; the earlier verdict above is historical. The coordinator subsequently identified a genuine unchanged `verified_done` proof taking 137.64 seconds. That finding was not part of the first review, and the earlier acceptance did not cover its operational consequences. No implementation was authorized on the strength of the stale binding after this finding.

Re-read both complete revised documents on 2026-11-01. Same source/base HEAD and independent reviewer instance. Current canonical UTF-8/LF SHA-256 binding:

| Document | SHA-256 |
| --- | --- |
| `docs/superpowers/specs/2026-11-01-overlay-books-design.md` | `dc8b90a5284a320d3acafdfddf54c2aef3a95f6791a8941389f21c4213e8e426` |
| `docs/superpowers/plans/2026-11-01-overlay-books.md` | `8f57f5d23934e250d5307da943675ddc57c674ff337d73f3494c3eef4d39f777` |

The revised contract addresses the operational finding without weakening acceptance: list and publish public Issue identities before enrichment, publish library before completion verification, then enrich and run the existing fresh verifier sequentially. A slow proof cannot erase an already arrived base projection. Actual source-fetch failures and deadlines remain explicitly unfinished/unavailable, rather than a promise of successful retrieval. Optional `on_update` receives independent public snapshots; default no-callback aggregate retains synchronous final return and existing completion semantics. No prior snapshot or manifest declaration is a proof input. Pending states explicitly cannot be Done, and only unchanged current-attempt `verified_done` can set verified/Done.

The producer/native boundary is now complete newline-delimited envelopes, immediately flushed and consumed before exit. Positive increasing sequence, final flag, attempt-scoped ownership, per-line 8 MiB, snapshot 10,000-entry, total 64 MiB and 32-frame limits are explicit on both sides. Capacity is reserved for a final frame, intermediate coalescing cannot suppress first identities, missing final/invalid streams cannot become success, and timeout retains latest validated partial data interrupted/stale. Last-success advances only on final ready; new refresh invalidates prior accepted displays immediately and cannot borrow old proof success. This is bounded incremental reporting, not a new verifier or proof cache.

Tests now directly own the crucial behavior: synchronization barriers prove callbacks precede a blocked verifier; a native controlled helper flushes identities/library then blocks, proving display before process exit and correct timeout retention; refresh invalidation, malformed/invalid UTF-8/nonmonotonic/after-final streams and cumulative caps are exercised. Browser tests also cover progressive/pending states. Public-only snapshot constraints and trusted native config/URL/message boundaries remain unchanged. Callback-isolation implementation details and frame-coalescing cadence are routine engineering decisions within these explicit semantics.

No blocking author questions or additional major contracts remain. Task dependencies and actual Windows evidence gates remain as previously reviewed. This accepts the revised specification/plan for implementation only; no code, proof performance, streaming harness, native UI or CI has been accepted by this document review.
