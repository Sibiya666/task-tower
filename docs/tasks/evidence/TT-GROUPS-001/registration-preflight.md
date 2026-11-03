# Task3B-R read-only actual implementation preflight

2026-11-03; /root/groups18_task3a_acceptor, acting as preflight author, not independent acceptor. **No implementation or specification approval is asserted.** Root full verification label groups18-task1rl-final-root is still running/pending. Checkout/source/docs/Git remained strictly frozen; only runtime artifacts were written. No SQLite database (including fixture SQLite), installed policy, native probe, model, credentials or network was opened/invoked. Source was inspected as text/AST.

## Exact basis

Foundation Task3A3e13f54d226ae33fc89ed3144658d0c53468f5e8 on accepted main7586df4ac2e59316521463b7526089c8314024e4; docs binding73186e6c58b6610eaa4f3e8745aca0437110e2f1. Current uncommitted Task1R-L v2 candidate has independent approval01c3aeff1572714e5ba1c90ba697fbc92bb83b76ae88fe00ef6ea062f74372d8, but no accepted implementation commit/full result is inferred. All15 candidate raw hashes were verified against runtime/groups18-task1rl-v2-source-freeze.json without mutation.

Read current8efc7e76-approved dated Task1R-L/Task3B-R design and plan additions, original R2/R3/OptionA boundaries, actual v2 loaders/guard, group_policy digest preimages, group_storage and both PipelineJournal._db validation phases. Design rawc7b385a65eb5ca1f463b64627334709c8ae80c20d7ebb4b367ce071ff9fb03b6; plan rawab21fd19146701a634faf1226d8facd0c87569161600d41666f892b3c9dbf195.

Static exact source/API/schema map: runtime/groups18-task3br-actual-map.json. It includes raw hashes and AST signatures for12 modules, all6 original table SQL/columns, all17 additive table SQL/columns and3 exact indexes. It recomputes original SCHEMAS digest5b37731384a2d5a8aa87f38f589bcced2b78db2205861e6aa5290d4b4ccdc9b6 without executing SQL. Preserve application_id1414808656/user_version2 and known catalog digest1e1e250b953b7166b481f9b52d9fa9a4ed1c6fa9454cd279600f51502315c96a. No DDL/schema amendment is proposed.

## Concrete callable map

Existing actual APIs:

- load_executor_config(path,connections): v1 four-key normalized output/max_active1..2; v2 version/capacity/profiles/allowlist/harness_resources, no max_active. Profiles remain unchanged. load_pipeline_config(path,connections,executor_config): actual tasks, normalized provenance and v1 LIMITS or v2 nullable capacity/noncapacity limits.
- capacity_policy.require_legacy_capacity(config,*,executor_config=None): raises UnsupportedCapacityMode(group_runtime_unavailable) for new config or nested executor2. watch_tick guards BOTH cached and freshly loaded runtime before recovery/helpers. Registration must load policy directly, not disable or bypass this execution guard.
- PipelineJournal(path,*,checkouts=(),forbidden_paths=()), operation_deadline(deadline), _pinned_database(), _existing_database(identity), _assert_existing(), _db(write=False,*,initialize=True). There is no public pin class, registration context, register_groups or registered_groups yet.
- group_storage.validate_v2(db,journal,*,objects=None), reconcile_legacy(db,journal), claim_fence(db,journal,run_id), _metadata/_typed_snapshot/_preserved_history/_positive_cleanup/_needs_product/_stopped. Current validator accepts unregistered legacy compatibility only and refuses all installation/epoch/resource/proof rows. Current leases/reservations require NULL epochs/unknown estimates.
- group_policy.load_group_config(path,connections,executor_config,pipeline_config), resolve_route(policy,repository,issue,task_id), group_binding(policy,task). policy_manifests does not exist: authority/capacity digest preimages are currently local variables inside load_group_config.
- PipelineJournal.submit(request,policy), lookup(delivery_id), status(run_id=None), history(run_id), claim(owner_id,max_active,*,queued_order=None). claim still validates1..2; a held unknown estimate globally blocks claims. submit still initializes legacy state and claim does not yet reject registered mode because registered data is currently impossible.

Required additions already authorized by the approved design, not existing setters:

- group_registration.RegistrationContext; load_registration_context(groups_path,connections_path,pipeline_path,executor_path,journal)->RegistrationContext.
- PipelineJournal.register_groups(context)->dict and registered_groups()->dict|None delegating to host register/discover.
- Explicit register-groups --connections C --journal J --config P --executor-config E --groups-config G --apply. No implicit registration by work/watch/adapter.
- group_policy.policy_manifests(policy)->{authorization,capacity}, preserving EXACT current digest preimages.

## Existing transaction/pin seams

_db write enters BEGIN IMMEDIATE, validates exact catalog plus validate_v2 and legacy rows BEFORE yield, then reconcile_legacy, legacy validation and validate_v2 AGAIN before commit. Registration must satisfy BOTH branches in the SAME transaction; it cannot temporarily suppress validation or leave an installation half-created. Deferred installation/epoch FKs permit atomic insertion.

_db read begins an explicit transaction only when an operation deadline exists. New discovery/consistent authority reads must enter operation_deadline and existing pin before opening _db(False,initialize=False), not combine separate status/history calls or assume autocommit queries are one snapshot. Existing nested deadline takes minimum; preserve shutdown4.8s rather than resetting it to60.

_pin_identity requires regular/single-link/no-reparse, st_dev>=0 and st_ino>0. _pinned_database holds a read-only OS file reference and checks fstat/path sameness; _existing_database prevents mkdir/initialize/recreation and forces URI mode=rw for writes. Reuse this boundary for J; use ordinary source file references plus exact raw-byte/fstat/path rechecks for G/P/E/C. Close all context references deterministically. Suggested internal lifecycle is context-manager/close on RegistrationContext, with60s deadline starting before source loading and retained through register, rather than a fresh60s on each phase. This is routine host factoring, not a JSON capability.

Current group_policy._paths covers G/P/J sidecar families and private placement; RegistrationContext must explicitly include executor/connections and all aliases/sidecars as the design requires. Pipeline _runtime currently has no groups_config handling. _fixed emits unchanged C/P/E/J argv, with dispatch paths for _dispatch; _backend_scope compares exact backend argv/cwd and every committed delivery fingerprint. Helpers must discover via same J, not add a flag to existing backend identity.

## Table/epoch/provenance map

Registration writes only:

1. group_installation: singleton1, immutable installation_id/canonical_journal/journal_file_identity_json/groups_config_path/bound_at; current_capacity_epoch/current_policy_sha256/current_authorization_sha256 advance under expected-old CAS.
2. group_capacity_epochs: sequential epoch/install ID/change_kind, raw policy/authority/capacity digests, nullable group/pipeline/executor/effective maxima, max_inflight, resource_policy_json/capacity_matrix_json/registered_at. Recompute minima; NULL is not fresh resource availability. Append only.
3. Existing group_reservations.capacity_epoch and every held/released legacy group_resource_leases.capacity_epoch bind the real first adoption epoch. Held known leases may materialize approved CPU/memory/pool only from matching original profile fingerprint/current explicit grant. Preserve action NULL owner/PID/input/epoch, observation_id NULL, original unknown state, held/cleanup evidence and component ownership. Missing/revoked profile remains unknown and globally fences. Later capacity epochs must not rewrite adoption provenance.
4. group_events binding/capacity_epoch closed bodies. First adoption enumerates all historical leases, including released ones; zero-lease clean reservations still bind adoption epoch independently. No resource observation, executable group action, group run, fairness cursor, proof, source/base epoch/update/phase is enabled by registration.

Exact event body approved: {version,installation,epoch,policy_snapshot,legacy_adoptions}. policy_snapshot={group,group_raw_base64,authorization,capacity,source_sha256}; source_sha256={groups,pipeline,executor,connections}; legacy adoption={action_id,run_id,profile_id,profile_fingerprint,capacity_epoch,estimate}, estimate null or {cpu_millis,memory_bytes,harness_pool}. Store canonical JSON and digest with current pipeline canonical_json/digest_manifest. Compare event identities/rows/epoch history; hashes alone never authorize registration or new actions.

Important implementation details:

- Current authority preimage is built BEFORE result.update adds policy_sha256/authorization_sha256/capacity_sha256. A new policy_manifests must reconstruct those exact prehash fields; blindly hashing the returned public policy adds self/hash fields and changes accepted digests. Retain v1/v2 baseline digest tests.
- Historical installation snapshots contain historical pointer values. Compare immutable installation columns across events, then validate the live pointer against latest sequential epoch; do not require an old complete snapshot to equal the updated live pointer row.
- Offline registered structural validation must never call current load_group_config/_project/_profile: those call _pins and filesystem checks. Factor/check the stored closed snapshot with pure types/digests/relationships. Live execution reload remains separate.
- Reconcile's current _reserve/_make_fence hardcode preG NULL epochs/unknown estimates. Registered cleanup cannot run that branch unchanged or erase actual adoption epoch/known estimate. Preserve Task3A migration snapshot/complete initial origins/later markers/order and original events/sqlite_sequence, and allow only original positive cleanup to release a lease.
- Backup hash/path and migration_id stay exactly as original metadata plus immutable migration event; registration does not create another migration/backup or reinterpret the diagnostic backup as authority/replay.

## Metadata, discovery and protocol ownership

Suggested unambiguous internal split: registered_groups()/discover(journal) returns typed existing-J metadata WITHOUT opening G/P/E/C or pins. Execution _runtime uses stored G path plus existing required C/P/E arguments to call load_registration_context and compare freshly loaded authority before effects. This satisfies offline status/cancel and same-J fresh discovery without an optional completion/authority Boolean. Public _status projects only fixed registration status/UUID/epoch/digests/counts; never raw stored paths/argv/pins/snapshots.

Existing lookup must retain known run/delivery identity under revocation; no not_found/re-admission/redelivery for a known receipt. Registered submit/claim and continuations must close regardless of v1 caller/max2/omittedG until actual4R consumers. Do not rely solely on Task1R-L config2 guard, because valid v1 files could address a registered J.

Pure wire work preserves exact old version dispatch: stage manifest1, role request/result2, host-check1, legacy unversioned receipt/checkpoint/publication bodies. New group versions are stage2/role3/host-check2/verdict-checkpoint-publication2/source-epoch1 and add exactly base_epoch/base_epoch_sha256/scope_base_sha/diff_base_sha/accepted_main_proof_sha256/task_delta_sha256. Actual signatures are in static map; stage_manifest checks is REQUIRED, not a default argument. Bind consumers to host journal run_kind/current epoch, never a model's supplied version flag. Pure schema fixture validity is not stage authority; executable group rows remain unavailable until later accepted4R/5 producers.

## Concrete scope question requiring coordinator ruling before an absolute claim

There is a distinguishability limit in the approved combination of unchanged v1 initialization and omitted-G discovery only from J. On a fresh process, missing never-created J with v1 policy/no G is observationally identical to a deleted formerly registered J with that same policy/argv. Actual _db(True,initialize=True) permits legacy initialization, and stored G/identity is gone if J is gone.

Explicit register_groups/context and positively known registered-J access can and must refuse missing/replaced J. This does NOT by itself prove that every fresh omitted-G v1 initializer can detect prior registration after total loss of J. Do not silently add an external binding sidecar/registry, new private policy field, automatic upgrade, or disable all legacy initialization to conceal this difference: those change the approved persistence/compatibility contract and need a separately reviewed proposal. Coordinator should either explicitly scope the noncreation promise to known registration/existing-file operations (lost-state bootstrap remains unknown/unsupported recovery), or obtain an amended durable external expectation/explicit initialization contract. This preflight does not choose or approve either. No destructive deletion probe was run; conclusion follows from actual missing-read yieldNone and legacy write-initialize branches.

Other factoring notes above can fit the approved contract without semantic change. A new hard bound should be applied to the prospective canonical registration event before mutation: group_storage._json already caps each stored body16MiB, while group_raw_base64 expands raw G. Oversized loaded policy must fail closed/rollback, not truncate snapshot or weaken validator. No broader policy hardening is proposed.

## Next authorized gates

Root must finish current frozen full suite, preserve independent approval/rejection evidence and commit Task1R-L before choosing Task3B source base. Rebind this map to that actual commit. Resolve the missing-J scope question and independently review any resulting semantic amendment before code; no accepting registration setter or source-G drift is admitted here.

Then follow proposed tests/API ownership brief runtime/groups18-task3br-ownership-brief.md. Current native Windows only; nativePOSIX61 deferred with applicable generic3OSCI retained. Original automatic hot recovery current Windows65 remains mandatory and unqualified by Task3A refusal/registration metadata. No whole18, PR/main, installed>=3 or night readiness claim.
