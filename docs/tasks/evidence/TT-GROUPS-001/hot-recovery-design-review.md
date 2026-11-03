# Independent Issue18 hot-journal recovery design review

Reviewer: /root/fetch_timeout_diagnosis

Verdict: BLOCK automatic original-file recovery in the current Task3A design. The genuine hot precommit case exposes a specification boundary, not a harmless test failure. No proposed generic RW/query_only fallback or clone-then-RW handoff is approved. A precise availability amendment and/or separately qualified recovery boundary is required before Task3A can receive current whole-scope acceptance.

This report contains design options, not implementation or permission to operate on the live journal. Existing source remains frozen; no original/live DB, journal, Git, authentication, process or task ownership was changed.

## Inputs and independently observed evidence

- runtime/groups18-task3a-source-freeze.json SHA256: 1b8ddfe1fbcf985f81782d0695f36904a2adacaa9cd5dce828d81df816877c0d.
- runtime/groups18-task3a-implementation-notes.md SHA256: 1a9efb1f5ba913891252b8c8e094e65e57e4d1d6e54984ee18c69d33d3461da2.
- runtime/groups18-task3a-hot-recovery-reproducer.py SHA256: 1964e8da5047865a4457a61784713fdd1e092be57192fb7e2318af35aad9f65f.
- Its retained JSON SHA256: 57c43db159145cfad60acf9f0a704f42a241fb58c5161933cccb4cdda73897cb.
- Source foundation is acceptedM4875381be68282a7ad77ab7b1c5a3898cbc09304. New main7586df4/fetch fix has not yet passed the reported repository acceptance barrier and is not silently substituted as accepted source.

Read the exact current migration algorithm and implementation handoff. The strengthened cache_size=1, exit88 before_commit case is the relevant actual page-spill crash; prior30/135 passing suites did not establish that case. The current32-test result with31 passing and one hot-recovery error remains the actual unaccepted scope result.

Independently reproduced the critical foreign-file effect using a separate disposable SQLite fixture, not any product/live DB: a committed application_id9999/user_version7 database, a child with cache_size=1 that spills an uncommitted262144-byte value and exits88, then first RO access. RO returned exact776 and DB/journal hashes stayed unchanged. A subsequent diagnostic RW/query_only access exposed appid9999 only after SQLite changed the files and removed the journal. The fixture was temporary; no product imports or original recovery were used in this independent experiment.

## Verified SQLite facts

SQLite checks for a hot journal before normal database reads. Recovery acquires PENDING and EXCLUSIVE locks, restores pages, syncs and removes/truncates/invalidates the rollback journal, then permits the read. A BEGIN or first schema query cannot be relied on as a host-validation boundary that occurs before this pager work. [SQLite rollback locking and hot-journal algorithm](https://www.sqlite.org/lockingv3.html#dealing_with_hot_journals).

Extended error776 specifically means that a readonly database needs hot-journal rollback. It says nothing about Task Tower schema, application_id, ownership, stopped controller or whether rollback is authorized. [SQLite result codes: SQLITE_READONLY_ROLLBACK](https://www.sqlite.org/rescode.html#readonly_rollback).

query_only rejects SQL data-changing statements but does not make the connection physically readonly; SQLite explicitly distinguishes it from a true readonly database. This is consistent with the fixture's pager recovery before appid validation. [SQLite query_only](https://www.sqlite.org/pragma.html#pragma_query_only).

Cache spill can flush the rollback journal and write modified database pages before transaction commit. Logical atomicity therefore does not imply that crashed precommit files are already a cold, immediately RO-readable old database. Turning spill off can move this boundary but cannot eliminate a crash during commit's writes. [SQLite atomic commit and cache spill](https://www.sqlite.org/atomiccommit.html#cache_spill_prior_to_commit).

Uncoordinated raw copies can mix database generations; a failed transaction's DB and recovery journal must remain paired. Deleting, moving, replacing or mismatching hot files is unsafe. This directly rules out copying a retained backup over live J or moving its journal aside to force RO opening. [SQLite corruption guidance, backup and hot-journal pairing](https://www.sqlite.org/howtocorrupt.html#backup_or_restore_while_a_transaction_is_active).

immutable=1 skips locks and change detection and assumes the medium cannot change. It is not a way to obtain a valid committed snapshot from a mutable spilled hot database; using it on original J would evade the required recovery/locking contract. [SQLite immutable URI](https://www.sqlite.org/uri.html#uriimmutable).

## The conflict in the current contract

The following three requirements cannot all be delivered by the present plain sqlite3 open/query sequence:

1. Every genuine precommit crash is immediately recognized and reopened as v1 by normal readonly inspection/retry.
2. The original file and journal are never changed unless full exact schema/history plus stopped-owner/controller preconditions are established first; foreign/newer/corrupt files are untouched.
3. Recovery uses an ordinary RW SQLite connection and validates those preconditions by querying that same source afterward.

This is an ordering argument, not a claim that no possible native system can solve recovery. For a hot source, the committed catalog/rows needed by2 are not safely available to ordinary RO SQLite, while3 may modify the source before returning them. Foreign appid/header, file magic,776, PID death, an old path/file identity or a retained backup path is not that missing current proof.

The accepted migration's BEGIN IMMEDIATE is useful after recognized cold validation, but it does not move hot rollback behind validation. The same distinction matters if a source becomes hot between cold preflight and opening the writer: byte identity pinning prevents some replacements, not same-file content mutation. State the actual stopped/cooperative-writer assumption and do not present before/after hashes as an atomic exclusion proof.

## Option A: safe immediate availability amendment

Recommended immediate design decision: preserve foreign-no-write and fail-closed migration, and explicitly separate logical crash atomicity from immediate RO reopen availability. This is a real amendment requiring fresh independent specification acceptance; it is not grounds to relabel the existing red test as a delivered original guarantee.

Suggested normative wording:

> Inspect and apply never recover an original hot journal. Exact SQLITE_READONLY_ROLLBACK is classified as recovery_required before any RW source connection, backup, DDL, controller claim, reservation or runtime effect. Report no accepted source version/catalog/ownership for the unresolved original. Preserve its database, journal and all sidecars without creation, deletion, rename or content change. A crash before the migration commit point preserves SQLite-recoverable old v1 state, possibly as a hot DB/journal pair; it does not promise an immediately RO-readable cold v1 file. A completed committed migration reopens as exact v2. Automatic recovery/retry of a hot pair requires a separately specified and accepted recovery boundary. Unknown execution/effect ownership stays fenced throughout.

Consequences: cold explicit migration can continue through its already specified recognized-source/no-clobber-backup/transaction checks. A hot startup is a concrete operational blocker, not a clean completion, foreign schema assertion or accepted migration. Do not advertise automatic crash recovery/night readiness or whole Issue18 completion while that boundary is outstanding. Root may retain Task3A as an honestly limited cold-migration substage with a tracked Windows recovery dependency; no POSIX deferral or manual owner questionnaire is needed.

Meaningful amended crash test: first strict RO operation returns recovery_required with original DB/journal hashes unchanged; no RW connection/backup/DDL is attempted. In the disposable fixture only, independently recover a private paired copy to prove old v1 logical schema, original rows/sequences and absent group DDL. That proves recoverability of this controlled fixture, not authority to recover or execute the original. Retain the previous failed32-test result and its former expectation as historical evidence.

## Option B: readonly shadow recovery for diagnostics only

A private DB+journal copy can be useful for analysis if it is a complete correctly paired capture with bounded paths/bytes, safe handles, an isolated directory and no SQLite connection ever opened to the original. Only the clone is allowed to perform SQLite rollback. Reject unexpected WAL/SHM/super-journal/ATTACH references and namespace escapes; SQLite's embedded sidecar references cannot be allowed to reach originals or external paths. Recovering arbitrary copied journals is not a trusted parser shortcut.

Without proven quiescence and continuous physical exclusion during capture, original/sidecar before-and-after stats or hashes do not establish a point-in-time pair: copying may span a writer, and ABA can restore observed metadata/bytes around mixed reads. At best report a recovered diagnostic snapshot with explicit original-currentness unknown. Never return an executable accepted-main/schema/owner proof, migration authorization, capacity release or accepted original version from it. A complete recovered clone still does not close the race to a later original RW open.

I do not approve clone-validate-close-handles-then-original-RW as a recovery algorithm. It contains an unfenced authorization-to-effect interval, including same-inode changes and owner/controller drift. Readonly cloning is optional evidence work, not necessary to implement Option A's untouched-source refusal.

## Option C: separately qualified original recovery boundary

If the original full automatic reopen guarantee is retained, recovery needs a new reviewed boundary that can reject before the first physical write/truncate/delete and keeps its proof tied to the same physical DB/journal throughout recovery. No such qualified boundary exists in this frozen Task3A implementation. It is not a one-line fallback.

One possible research direction is a narrow recovery-only native VFS/helper that uses the same pinned source handles and SQLite-compatible locks for the entire validation-to-recovery interval. SQLite provides distinct file I/O/lock and VFS deletion hooks, but exposing those hooks does not by itself prove a safe implementation. [SQLite file I/O methods](https://www.sqlite.org/c3ref/io_methods.html), [SQLite VFS interface](https://www.sqlite.org/c3ref/vfs.html).

The following are mandatory design obligations before such a proposal could be accepted:

1. Atomically obtain effective exclusion of relevant writers and namespace changes without first permitting pager recovery. Define the Windows handle/share/locking interaction and prove it works with the actual SQLite connection. A cooperative named mutex alone does not exclude an ordinary external SQLite writer; an OS deny-write handle that must be closed before SQLite can open RW creates the same handoff gap. Neither is a completed proof.
2. Under that uninterrupted fence, capture the actual original DB and all relevant sidecars from pinned regular single-link no-reparse handles into a complete private snapshot, with strict size/time limits. Prove pair consistency, journal association and absence of forbidden super-journal/ATTACH/WAL cases; raw filenames/digests alone are not an authenticity guarantee. Recover and fully validate only the isolated clone before any original write. Validate the exact old schema/history, physical source binding and stopped controller/no-conflicting-live-owner requirements from genuine state. Historical migration intent can supplement provenance, not replace current proof.
3. Keep the same physical identities, namespace binding, journal bytes/generation and exclusion continuously through the first source recovery I/O. A changed file, journal, owner, lease or deadline before that write aborts with untouched source. Do not drop/reacquire the fence between clone validation and original recovery. Reject arbitrary already-foreign sources, including same appid and a copied old journal/intent; no self-declared operator Boolean grants recovery authority.
4. Authorize only SQLite's rollback of that proven pair, using existing-only file access and no SQL schema/run-state mutation or claim initialization. This is not PipelineJournal._recover_existing: that helper's runtime-state transitions cannot substitute for pager-only recovery. Do not run arbitrary SQL from clone/source, attach external files, copy a backup over J, redirect backend identity or release unknown execution.
5. On success, still validate the now-cold original schema/history/rows/sequences against the proven recovered snapshot before any normal migration. A recovery exception or crash retains a bounded unresolved state and original pairing, not success. Fresh ordinary migration gets its own explicit invocation and preconditions; no blind replay is appended to a recovery attempt.
6. Prove actual Windows behavior, interruption and deadlines with real multi-process faults and physical file races. A supported standard-library-only implementation may not expose the required at-I/O boundary; assess that as an explicit architecture constraint instead of bypassing it through undocumented CPython handles or unreviewed ctypes tricks. New native dependency/helper/VFS scope requires an accepted design. POSIX remains separate future scope.

This is a set of proof requirements, not approval of a specific VFS or an instruction to build one now. If they cannot be satisfied under current constraints, retain Option A's honest blocked state rather than relax foreign-no-write implicitly.

## Rejected shortcuts

-776 or generic READONLY -> ordinary RW/query_only -> validate afterward: demonstrably changes foreign data before refusal.
-SQLite authorizer/query_only, BEGIN EXCLUSIVE, journal_mode switch, cache_spill changes or immutable/nolock flags as authorization: none supplies pre-recovery host proof.
-Header-only appid/version, same path/inode, old backup/migration receipt, process death or task/operator assertions as current catalog/cleanup proof.
-Recover clone then replace live J; rename/delete/zero original journal; restore backup over original; reset rows; import into another claimed J; retry an unknown effect or free resources from recovered projected state.
-Weaken the real hot-crash test to a cache-only cold fixture, or cite the old30/135 green results as full hot qualification.

## Required fault-test matrix

For Option A, assert real cache_size1 precommit spill -> first RO776 -> fixed recovery_required, byte-for-byte unchanged original DB/journal/sidecars, no writer/backup/DDL/native calls and no schema/ownership approval. Cover own6-table v1, foreign appid9999, foreign schema with Task Tower appid, newer version, corrupt journal, truncated/mismatched pair, unexpected super-journal/WAL and permission errors. A non776 error must not enter any recovery branch. After-commit crash must yield complete recognized v2 without preparatory RW access. Preserve old rows/sequences/fences and prove no replay/resource release in both states.

For any future Option C, add real concurrent writer/page-spill, owner/controller liveness change, same-inode byte mutation, path/journal replacement, ABA, hardlink/reparse, sidecar arrival/removal and clone-to-original handoff barriers. On every failed prewrite proof assert zero original writes/truncates/deletes. Crash during capture, clone rollback, before first original I/O, mid-original rollback and post-sync/pre-validation must preserve truthful retry/block classification; no new executable ownership. Enforce one shared deadline under stalled locks/I/O and injected backup/disk-full failures. Compare recovery's final original semantic dump and SQLite sequences with the initial committed v1 state, never only a version integer. Verify negative static/foreign cases and races with effect-level write instrumentation as well as hashes.

## Root decision and integration

Recommended: adopt Option A explicitly now, track Option C as an unresolved Windows recovery requirement if automatic hot reopen is a product requirement, and obtain fresh affected-spec review before changing the red expectation or code. Option B can supply diagnostics only. No current design is approved for original hot recovery. The frozen Task3A partial remains unaccepted until the chosen contract and its meaningful tests are accepted; full Issue18, native resource concurrency and automatic night readiness are not established. Respect the new main63 acceptance barrier and re-audit actual accepted source before branch integration.
