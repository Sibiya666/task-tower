# Independent Issue17 accepted758 Task3 specification binding review

Reviewer: /root/groups18_task3a_acceptor, distinct from Issue17 document author. Date:2026-11-03. **Verdict: APPROVE the exact three-document Task3 binding amendment below.** No blocking specification finding identified. This is fresh affected-specification acceptance only, not implementation/test/native-pilot/whole17/PR/main acceptance or external writer authorization.

## Exact document binding

Independently recomputed raw SHA256:

| Document under task-tower-pr-worker | Raw SHA256 |
| --- | --- |
| docs/superpowers/specs/2026-11-02-pr-worker-design.md | 1d1897dc1222669d9518f61bf03978097688c4c5cc3a0a8954f3372f788fe763 |
| docs/superpowers/plans/2026-11-02-pr-worker.md | a6547fb654dfaba27d51bab90276d6509ae1f693fa2a1855a36816a3c1149491 |
| docs/tasks/evidence/TT-PR-WORKER-001/accepted-main758-task3-preflight.md | 7772df8bdd9d830fecde252df349132babde06e4cb8c304b23633520b9034937 |

Read repository AGENTS, actual specification/plan and scoped preflight; inspected the actual tracked two-document diff plus new preflight. Consulted accepted Task1 R1 and Task2 source/reviewer contracts, actual PRJournal BINDING/PROOF/payload/observation/begin_effect/ownership/publication guards, Task2 canonical authority consumer, and immutable accepted758 pipeline/publication/reviewer/postmerge/task completion source. No implementation, source edits, journal opening/writing, model/native/auth/install/network effects or Git mutation occurred. Only this private review report was written.

## Six concrete bindings

1. **Trusted authority and consistent snapshot:** spec67-71/plan77-78 provide host-only StageAuthorityContext with genuine configured journal, normalized loaded task policy, current fingerprints/criteria and identity-bound immutable object reader. Its output retains accepted Task2 authority field set; public MD/PR JSON cannot construct authority. One explicit RO transaction under accepted pin/existing-file boundary reads run/history together. Missing/replaced/WAL/hot/locked/unknown source refuses without recovery/init/RW fallback. It expressly distinguishes snapshot consistency from current effect authority. The implementer must actually BEGIN before the validation/read series when using accepted _db, whose implicit BEGIN is conditional; the contract already requires this, not an API change.

2. **Genuine receipt/contribution/final publication proof:** spec71 requires actual attempt/process/contribution/rework/supersession and prior-receipt edges, not only project_evidence's partial reconstruction. Accepted project_evidence checks accepted stages and emits ONE MD; accepted _final/_commit_object also depend on mutable original worktree, so the new immutable object validator correctly reproduces exact parent/tree/message/change set and bytes independently. Accepted test manifest checkpoint remains final host commit parent; run.checkpoint_sha remains final PR head. Push/pr_create typed effects, minted marker effect identity, repository/task/Issue/author/current PR binding remain required.

3. **Compatibility bytes and stage records:** spec73/plan77-80 use strict base64 plus raw digest and original scheme digest, avoiding Python bytes in Task2 canonical JSON. Accepted pipeline canonical_json uses ensure_ascii=True/allow_nan=False; designated v2 artifacts reject BOM and canonical_text normalizes CRLF and lone CR. Accepted tasks v1 hash normalizes only CRLF and retains BOM/lone CR. Three compatibility stage records may legitimately reference the same reproduced host MD while retaining separate genuine receipt/reviewer authorities; no fabricated three-file projection or tracked card overwrite is required.

4. **Preintent identity, real process, durable envelope:** spec75-77/plan81-82 define preallocated distinct reviewer UUID, exact request/bundle/snapshot/merge/pin binding and actual PID/exit/started/cleanup proof, with no label-as-instance shortcut. ReviewRunner.review_bound is additive; legacy review returns its existing bare result. Immutable envelope must be persisted before save_review/_apply and later row reuse must match exact completed envelope/result/bundle/effect. Orphan running/unknown or unmatched legacy rows cannot launch again or confirm a new effect.

The request digest rule is compatible with actual PRJournal.begin_effect: its postmerge payload accepts reviewer_instance_id, request_sha256 and merge_commit, validates owner/barrier/current binding, then mints effect_id. Hashing the canonical request with binding.request_sha256 and binding.effect_id omitted therefore permits preintent hashing without self-reference or knowing a future UUID. After begin_effect, the final request contains the actual effect ID, and receipt_sha256 hashes every other envelope field including that request, result/process and identity. The same prehash alone cannot substitute another effect: matching exact durable intent/effect and final envelope binding remain explicit requirements. No accepted PRJournal schema change or relaxed payload is necessary.

5. **Publication context and noncircular completion:** spec79-81/plan83-85 supply genuine connection/source/current-main and exact PR/Issue/task/merge/barrier plus validated host receipts. Accepted GitHubPublisher needs full Issue ID added after receipt construction, and its existing publish batches POST/PATCH; additive publish_step preserves legacy default/public v1 bodies while separating each effect. Accepted verified_done validates trusted lifecycle/receipt/latest bundle/ancestry but not live closed/completed state itself; the amendment explicitly requires both separately, plus authoritative exact main. publication_completion_proof accepts closure_observed and produces existing Task5/PRJournal PROOF fields, including publication_id, without first demanding published. publish_step records published+proof; Task5 subsequently validates same proof/acknowledged effects and releases the barrier. This removes the circular dependency without new public receipt fields or callback Boolean authority.

6. **Owner-loss observation only:** spec83 and plan85/Task5 retain accepted PRJournal's active-owner/CAS restrictions. Lost/retired owner's GET inspection returns positive facts only and cannot call observe/record_publication or take ownership. Only unchanged still-live owner may persist a unique matching observation and proceed on a later tick after fresh proof. Absence, clock expiry and restart do not grant replay.

## Accepted-source verification

Recomputed all eight raw source hashes in immutable runtime/postmerge-worker/releases/7586df4ac2e59316521463b7526089c8314024e4; every one matched the preflight:

- pipeline_journal.py d4a142f83f2efe4badf288faf6690d7d46ffa7a94f4af8cd2ac3b9da12e3573c
- pipeline_inputs.py 4ac7678e4f26cbc58bf7516d5cdc9fa374fa97e62541b7c3b5f7d10a0ff8dbe5
- pipeline_publish.py f2b636778701ee28f9c8d95600ba158839e7bf14b70b2c84fd848392c3e6af04
- postmerge_worker.py cb47197c66737129854350a1b1c2a115b3c0c135695f0172fd792df6d8db9ced
- github_publication.py 82d4613914e10e90140d8b53c3b18ea1e766222533dc7a7adf602af366cd2509
- reviewer.py 3f31b0bfd4907026be0f8c78ba5b3c5f97b86a1b8fc659c2f908145430f045d6
- project_worker.py d0a021c598f9109f47fa80001bcba206c18fcf50f80bd12fb5c0abfc27eba0c3
- tasks.py f08ef728e6a19a22b9a43dbcdd94d5c35c56f27334ab7245960a703088271a65

No test execution or PASS claim is needed for this documentation-only spec review. Plan requires meaningful RED then actual SQLite/Git/process/transport and complete regression evidence after implementation. Accepted main must be integrated into17 before imports; source drift invalidates this binding.

## Limits and declined-to-judge

No source journal/schema mutation, new public receipt identity, fake Boolean verifier, JSON callable import or organizational-label process identity is authorized. Generic three-OS CI remains mandatory; dated Task3 amendment explicitly limits current native qualification to Windows despite historical broad portable-platform wording.

Actual all-main-writers operator authorization and effective strict nonbypass server protection proof remain external installed-pilot prerequisites. Current chat, admin permission and local lock cannot manufacture them; fixtures cannot qualify the genuine autonomous pilot. This review did not browse or verify changing GitHub endpoint behavior: existing external API contracts are unchanged by this amendment and still require official-source verification at implementation as the plan says.

Declined to judge: future Task3 code quality/correctness and RED/green results (not written); current remote writer/protection/account state (no network/native/auth effects permitted); installed pilot and final17 completion (later mandatory gates); previously accepted Task1/2 whole implementation beyond compatibility seams inspected here (their independent verdicts remain separate). No unresolved specification blocker remains in the requested binding amendment.
