# Issue17 legacy provenance binding proposal — not approved

2026-11-03. Source-only inspection of accepted758 and Issue17. No live journal, native harness store, credentials, import or installation was opened/changed. This proposal adds no accepting legacy loader. Current missing/unsupported provenance remains needs_input. A file/hash/account assertion alone cannot recreate original process evidence.

## What the actual old contracts retain

`tasks.py` v1 stores executor and per-stage reviewer organizational strings, evidence relative paths/digests/schemes, accepted status and postmerge commit/main_ref. `accept_task` validates prior evidence and that reviewer string differs from executor string. It records no stage attempt/instance UUID, original launcher/PID, command/profile pin, process/result/request envelope, lifecycle cleanup or authenticated original stage attestor. Existing spec-review MD can name an agent path and bind document/head hashes, but prose is not a retained process record. Example current TT-PR-WORKER-001 card executor is pr-worker-implementation-team and spec reviewer pr_worker_spec_review; neither may be renamed into a new purported original UUID.

`postmerge_journal.py` reviews store task_id/commit/snapshot/status/detail/result. Legacy ReviewRunner returns bare task_id/commit/verdict/summary/findings; no original instance/process envelope. This journal cannot supply spec/development/test provenance, nor reconstruct missing postmerge process identity.

`executor_queue.py` has jobs and attempt_history containing delivery/run/attempt/attempt_id, owner_id/owner_pid, profile fingerprint and process evidence. These prove bounded foreground execution only. They contain no accepted spec/development/test chain or independent stage reviewer receipts. execution_completed is not stage acceptance. A queue owner is not a new authenticated stage-reviewer UUID.

Integrated16 PipelineJournal DOES retain genuine stage instances/attempts/receipts/contribution/effect edges. Its supported reader is the pipeline source path already defined, not a reason to relabel unrelated old cards or reinterpret queue admission as a stage verdict. The new Task3 bound postmerge envelope likewise concerns a new postmerge launch, not historical stage execution.

No original legacy stage process records have been established by this source-only investigation. That is a concrete evidence gap, not evidence that no user-retained records can exist. No live records were searched to resolve it.

## Proposed closed import document (requires fresh spec review)

Top-level exact fields `{version,records}`; version exactly integer1; records a nonempty bounded object (max1000). Each object key is the literal canonical compact JSON of `[repository.casefold(),task_id,issue,issue_id,pr_number]`, using ensure_ascii=True, allow_nan=False. E.g. `["owner/repo","TT-LEGACY-1",9,900,44]`. Reject noncanonical spellings, unknown/duplicate keys, bool integers, missing immutable Issue ID, foreign account/repository or repeated identity. Key encoding is an identity locator, not an attestation.

Each value has exact fields `{repository,task_id,issue,issue_id,pr_number,head_sha,base_sha,criteria_sha256,card_path,card_raw_sha256,importer_account,stages}`. Key and embedded identity must match. card_path is the exact installation-mapped safe relative docs/tasks/TT-....json read from immutable head; raw bytes and unchanged v1 stage evidence schemes/digests must validate. No new v1 field is added. importer_account must equal existing private project publisher_account in v1: this reuses an existing explicitly trusted installation identity without granting a new credential scope. It restricts who may perform a genuine import; it does NOT authenticate missing original records. This account restriction is proposed technical policy, not operator authorization or proof the account controls all main writers.

stages has exactly spec/development/test. Each stage has exact fields `{executor_source,reviewer_source,verdict_source,evidence}`. Each source locator has exact `{resolver,path,record_id,raw_sha256}`. path is an existing safe absolute private retained-source path outside all connected checkouts, with alias/hardlink/sidecar collision rejection; raw_sha256 identifies bytes, never grants authority. evidence is exact `{path,sha256,scheme}`, preserving the original card's v1 record. No UUID/process fields may be supplied merely by the importer: they must be read and validated from a supported original host source.

## Resolver candidates and honest first-version gate

1. **Accepted pipeline-journal-v1:** genuine current private pipeline reader can validate original source records and all roles; already supported by `source=pipeline`. Do not add it to legacy automatically: current policy selects exactly one source and rejects unused/ambiguous authority. A legacy import from that source would require an explicit separately reviewed policy/schema binding and the actual same task/card/head relationship. This does not solve old chat-only cards.
2. **Executor-queue-v1:** reject as incomplete stage provenance. It has real attempt/process evidence but lacks independent accepted stage chains. Do not allow a verdict MD to fill that hole.
3. **Native harness retained sessions/logs:** no closed supported resolver can be specified from the actual old Task Tower code. Original session UUIDs/PIDs can be useful only if their real authoritative schema also binds exact role/input/result/commit/cleanup and independent verdict; a session name/agent path, screenshot, copied JSON or public prose is insufficient. No parser for unspecified Codex/Claude internals, no DB mutation, no minted UUID or cleanup inference.
4. **Future host-stage-envelope-v1:** proposed retained source format could carry original repository/task/Issue/role/stage/input/commit/profile/instruction identities, original instance/attempt UUID, actual process proof, immutable result hash and the host-attested acceptance receipt. Such a format would need an identified original producer/trust root and contemporaneously retained records. Writing a new format now cannot retrospectively authenticate old executions. Therefore no accepting implementation is authorized by this proposal alone.

**Proposed first-version behavior pending review:** parse/reject malformed wire documents and report `legacy_provenance_unsupported` for all currently unimplemented resolver IDs. No accepting legacy path until one actual original host-record schema/producer/authority boundary is identified and independently accepted. If the milestone insists on accepting existing manual/chat legacy tasks, it remains blocked by genuinely missing retained role evidence, not an installer prompt or arbitrary private import signature. Root should choose whether to scope v1 as pipeline-only with explicit legacy admission refusal or supply a genuine existing retained source for a fresh resolver design. No option can turn importer trust into invented original process facts.

## Required refusal tests before any accepting resolver

- Same public card/evidence plus self-consistent private JSON hashes still fails without supported original records.
- Importer/publisher equality cannot fill absent role, attempt, process cleanup, input or verdict edges.
- Executor-only queue records cannot become independent stage acceptance.
- Missing original UUID cannot be minted; organizational label cannot be relabeled as original process identity.
- Current source/pr/card/criteria drift, duplicate identity, source aliases, foreign immutable Issue ID and unsupported source versions park without writes/import/recovery.
- Genuine accepted pipeline source continues independently; private legacy errors cannot grant it authority or block unrelated pipeline work.

No spec/plan modification, legacy import setup, accepting stub, native probe or approval claim is included here.
