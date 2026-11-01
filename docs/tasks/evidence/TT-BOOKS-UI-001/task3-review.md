# Task 3 independent policy review

Verdict: **REJECTED** (2026-11-01). Reviewer: independent books_policy_review instance; implementation files were not changed. Scope is only overlay/web/books-policy.js and overlay/test-books-policy.cjs on feat/books-ui, base 4758905. This is not PR or native UI acceptance.

Read the complete implementation and test source, repository AGENTS, accepted design and Task 3/common interfaces. Current accepted spec binding is dc8b90a5284a320d3acafdfddf54c2aef3a95f6791a8941389f21c4213e8e426; plan binding is 8f57f5d23934e250d5307da943675ddc57c674ff337d73f3494c3eef4d39f777. The bottom current verdict in spec-review.md supersedes its historical binding.

## Exact source binding

SHA-256 over UTF-8 without BOM, normalized LF:

- overlay/web/books-policy.js: 4cf74b24222806087167f2469142c1e2ef29be8229fb871e5fe804a07ddc612b
- overlay/test-books-policy.cjs: 13d79fa529efee52820efef480e93d07a48f5f8473c51beec7ddfa65d9486421

## Fresh verification

Node v24.22.1. Command `node --test overlay/test-books-policy.cjs` exited 0: 10/10 passed. Full source inspection and independent inline Node probes nevertheless found two blocking gaps:

1. **References migrate to another record's page.** Build feature rows for parent o/r#1 with expanded children #2, #3, #4 and unloaded #99, with the first three children loaded and their native parent #1. Page 0 contains records #1,#2,#3 but no #99 reference. Page 1 contains record #4 and the #99 child-unloaded reference with owner #1. `pageRows` uses the preceding record rather than explicit owner. This violates the common interface requirement that references/warnings belong to their record, loses the relationship on its owner's page, and shows it beside an unrelated child. Fix ownership-aware pagination and add this mixed loaded/unloaded expanded-child regression; retain the global three-record quota.

2. **Unknown nested library metadata survives normalization.** A valid immutable library entry augmented with `milestone:{repository:'o/r',number:1,token:'SECRET'}` and `issues:[{token:'SECRET'}]` is accepted by normalizeEnvelope and returns both token fields unchanged. The common interface requires issues to be qualified identity strings and milestone to be a typed repository/number association; unknown metadata must not cross the public projection. The library copyFields path currently copies both structures without field/type checks. Reject or safely project these structures and cover unknown keys/wrong types with regressions. Audit other raw structured copied fields against the common interface as part of the fix.

Both independent probes exited 0 and printed the erroneous outputs, rather than relying on the submitted passing expectations. Findings were sent to the coordinator for implementer correction. No implementation changes, commit, external writes or native acceptance were performed. Re-review revised source and bind new hashes before accepting Task 3.
## Additional scope of blocker 2

A second independent normalization probe confirms the same defect also applies to Issue `status` and `remote_state` (objects accepted), relationship parent `source` (object accepted), and milestone `title` (object accepted). Each accepted object retained `{token:'SECRET'}` unchanged. These are declared typed public fields, so the remedy must cover all copied structured/scalar field contracts, not only library associations. `relation` currently validates Issue relation id but blindly copies source; milestone validates only id before copying number/title/source. Provenance fields do apply a recursive known-key projection, and phase/blockers/results/history have selected checks, but those do not protect the raw copy paths above. Add scalar-type and nested projection regressions for these paths.

## R1 independent re-review (current verdict)

Verdict: **REJECTED**. The two original blockers are corrected: pagination now indexes attachments by owner, and scalar/association objects cannot pass through raw copy paths. Fresh `node --test overlay/test-books-policy.cjs` exited 0, 13/13 passed on Node v24.22.1. Inspected both full revised sources and compared retained fields to actual accepted Task 1 book_projection.py, capture.py and capture_migration.py.

Current canonical UTF-8/LF bindings:

- overlay/web/books-policy.js: b3543b385133cd7f8baf083c3a6d5e0564ccaebffc89fd1b800fd2f76250355a
- overlay/test-books-policy.cjs: b90268b04220d20179773f63962a809dd102e3bfad9492977fccc763705e84c9

Remaining compatibility blocker: valid public provenance is silently discarded. Python capture_projection emits requested_relations with optional sources (a validated safe URL array), but the JS provenance allowlist has no sources key. Python book_migrations emits number, source_sha256, status and issue_url; JS drops source_sha256. A fresh independent inline Node probe supplied capture.requested_relations.sources:['https://github.com/o/r/issues/2'] and migrations:[{number:1,source_sha256:'a'.repeat(64),status:'migrated',issue_url:'https://github.com/o/r/issues/1'}]. Output contained requested_relations:{} and the migration without source_sha256. Probe exited 0 and printed the loss. These are established public provenance/identity fields, rather than unknown metadata; retain them through explicit bounded typed projections and add a compatibility regression. Stage status/commit and current remote-attempt/history fields are retained by inspection. No source changes or commits by reviewer.

## R2 independent re-review (current verdict)

Verdict: **ACCEPTED** for Task 3 pure policy implementation and tests. This section supersedes the rejected source bindings above while preserving their findings/history. No blocking findings remain in this reviewed scope. This is not whole-diff PR, native bridge, UI, merge or postmerge acceptance.

Canonical UTF-8/LF SHA-256 bindings verified by reviewer:

- overlay/web/books-policy.js: a73fa4b73cd81d6e8ae9524118f39458cad46febf535bdc6c8adad332d1eb507
- overlay/test-books-policy.cjs: 779003f71284c2122c2a1aba9849c81c10c35046063fc7dd41ebe6ccc90d69c0

Fresh `node --test overlay/test-books-policy.cjs` exited 0: 15/15 passed, Node v24.22.1. Inspected the revised policy/test sources, including owner-indexed pagination, strict scalar/association projections, bounded known-key provenance, library path/version identity, limits, pending/freshness and hierarchy/filter behavior. Compared supported public fields to the accepted Python Task 1 implementation: book_projection.py, capture_projection/relationship_projection in capture.py, book_migrations in capture_migration.py and book_library.py. Current stages, attempt/review/history, capture requested relationships and promotion, public migration identity, explicit library associations and uppercase Markdown suffix survive the normalizer. Declared library acceptance remains source state, independent from verified task Done.

An independent inline Node assertion probe (not the submitted test expectations) exited 0 and printed `Independent R2 preservation/unknown-field/immutability/owner-page assertions PASS`. It combines a capture source URL containing a query, migration source_sha256, nested unknown token fields, an expanded parent with three loaded children plus unloaded #99, and checks input immutability, exact valid provenance retention, unknown-field removal, three-card quota and owner attachment on both pages. The unloaded reference is now present with parent #1 on page zero and absent from the child-only second page. Existing original metadata object faults remain covered by typed validation; the added source/hash fields have bounded type validation rather than raw copying.

No implementation files changed and no commit made by reviewer. Stream ordering/attempt admission and native source launching remain Task 2 responsibilities; DOM interactions and actual Windows evidence remain later independent gates. Changing either bound file invalidates this acceptance.
