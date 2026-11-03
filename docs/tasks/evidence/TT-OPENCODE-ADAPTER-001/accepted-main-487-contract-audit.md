# Actual accepted-main487 contract audit

Reviewer: /root/fetch_timeout_diagnosis. Read-only source/AST/Git audit after genuine Issue16 closure. No product imports, SQLite opens, runtime/probe/model/auth/install actions or source edits; only this report is written.

## Accepted foundation and gates

- Accepted main: `4875381be68282a7ad77ab7b1c5a3898cbc09304`; PR42 head `6e062691b1d668a41b39b56c2895a41c6ddfcb8b`, base `d5cf8953b70caf5329d5173b7fb4a15eaa4df978`.
- Actual M/H tree identity: `99332ee2d691d8e741abd9fc8ac8dbc364b863ca`.
- Postmerge CI run41503463955 attempt2 passed Windows125497632980, Linux125497632881 and macOS125497632722. The first-attempt macOS no-runner cancellation remains preserved separately; attempts are not mixed.
- Native independent exact-M reviewer APPROVE, evidence SHA256 `ac8d0687173cb7a0ce3b7e5ce2763b7d86d48ead8d565853215939fe0c41aef4`. Reviewer honestly relied on supplied verified CI because its local Python could not start; no local passing run is invented.
- Automatic publisher identity `17e4cc1b4297b8c98fffef1393e2808dea955c56ec0e3cf6fa86af8a57476623`: published; unique actual receipt https://github.com/Sibiya666/task-tower/issues/16#issuecomment-6595253516 . Issue16 closed2026-11-03T04:15:13Z (07:15:13 Moscow); native Project Done. The existing finalizer succeeded and checked exact current main/PR/CI/receipt/Project.
- Original checkout HEAD remained `66d3aa74ed528e1d08daec544233386dca1a77e2`. No legacy delivery/backend identity was redirected. Prior mainD5 failure and attempt1 history remain intact.

The source API gate in the provisional preflight is now satisfied for this exact M. This audit is not downstream specification, development, test, PR or native acceptance. It permits a precise accepted-base handoff; subsequent main changes require another affected-interface re-audit.

## Recomputed committed identities

All14 canonical module hashes match the provisional candidateH preflight. All42 deployed Python modules are raw-byte identical to the actual M Git archive. Raw working-file hashes in the older preflight can differ from committed/archive bytes because some working files were LF while committed/archive files are CRLF; canonical identities match. This is not a source change. Canonical hashing here decodes UTF-8 BOM, normalizes CRLF/CR to LF and re-encodes UTF-8; raw hashes below describe committed Git/archive bytes, not working files.

| task_tower file | Committed raw SHA256 | Canonical SHA256 |
| --- | --- | --- |
| pipeline.py | 5af888019504a829b99ac56a194b6156c790d00f90d20405ac844d88d055890a | 233d20d9324c554d886f912f61c52976d01cb882cf0522a67ab2f65cb86b5931 |
| pipeline_journal.py | d4a142f83f2efe4badf288faf6690d7d46ffa7a94f4af8cd2ac3b9da12e3573c | c86e51acc4ae87e199a08c6982f7fb0debcab4e0a7a2fd1e2d59ec3bbd13fa66 |
| pipeline_policy.py | d647350842ee3aa2610b465f5189387a0a14d7bb862671126e84dc6965fd19b1 | 1b677caee3cd41d947218f080df46ba62ddb0e659d2b50a00cfa8931e1fa7e0f |
| pipeline_inputs.py | 4ac7678e4f26cbc58bf7516d5cdc9fa374fa97e62541b7c3b5f7d10a0ff8dbe5 | 88eb9edab82264695f32de485218caab7beefc3bde72b290e49e76af47ef00a2 |
| pipeline_roles.py | cbadb85abe631906d7b9d27a6d0d83705d1afe6b78eb299a2eb5a95acff2eb09 | 15422eae2391db22d5ce8905337166736470eca6d5f13250e026c12d2d7507b9 |
| pipeline_publish.py | f2b636778701ee28f9c8d95600ba158839e7bf14b70b2c84fd848392c3e6af04 | b2334db53619d698cf2e88719459d9533a0ed0cc0aff885a085cd0d981e43603 |
| pipeline_worker.py | 8e64df3ff9d77c6b43631b07e3709725fd285c900a70248347f5c1801b3bc650 | 3ac0ab44af3b67862b310f252b915fd98ab29bec120066707123e68c3e036dcb |
| executor_profiles.py | 89853bb99866fe62312966bd3e629e9c967305f5755f116f751b547b00bd50f4 | b80944cceefcb359f4be6597b1780227cb7525da08e2d8c626f6b9b8f4a5d901 |
| executor_harness.py | 6d2baa0165194cdbbae01973c05bcfa0d53702a5713f5c8ee9c8240d5bf824cb | d8c885c0287958459eda6e2eab98964e30b99e56d9a0b151326c2d544c806682 |
| executor_worker.py | 51642df305c7245c0d473b6c32d7f77641d5669cc03f28d22a4fb64d79039341 | 468f1cd11f441c2ac7b614a7f953d1824979850582ed014386f8dfd5d2a0ef33 |
| processes.py | e3c07d5cdff3ad123b92f188fb62d5e03f63c83d024f89ab549ef1058ace52bd | 329bd49d2fb8a155b6eb0002bd43876d003e921081041cfa73f41a09595a890c |
| windows_job.py | 9212e216cb52bc55e77ebf0854b86f502b851f74fc26a667b105d4c90085498a | df5f7de7b6f7e5324070c78422159286222c4b0dfdba2e4ae53d85d8e9b775fe |
| executor_queue.py | febd031b51a835900e1bc4fad8548f3779e09afff3caa35e3ae80e1a8acf01b3 | ead14695dd319def66baa4ecbfab8e6259e8ab97edc49ac87f9c0419803dd11c |
| dispatch_delivery.py | 08d35b75df383b27d6dd7d47ee2a8315f1efd1d04f3767afbfb9552d0afcf605 | c5f247aa6433b84e7db814ffe3b32e2d8e7dd2fc3e3cfdd562448adb8c58bbb4 |

## Frozen v1 journal and ownership composition

AST literal SCHEMAS canonical JSON SHA256: `5b37731384a2d5a8aa87f38f589bcced2b78db2205861e6aa5290d4b4ccdc9b6`. Application_id1414808656, user_version1. Exact original catalog is six application tables: runs, attempts, verdicts, effects, events, controller, plus SQLite's sequence bookkeeping for the AUTOINCREMENT events table. No group tables, resource leases, base epochs or migration API exist in M. The original six SQL strings are frozen below without running SQLite.

```sql
CREATE TABLE runs(run_id TEXT PRIMARY KEY, delivery_id TEXT NOT NULL UNIQUE, repository TEXT NOT NULL, issue INTEGER NOT NULL, issue_id INTEGER, task_id TEXT NOT NULL, runner_label TEXT NOT NULL, profile_id TEXT NOT NULL, profile_fingerprint TEXT NOT NULL, policy_sha256 TEXT NOT NULL, criteria_sha256 TEXT, superpowers_sha256 TEXT, source_sha TEXT, base_sha TEXT, checkpoint_sha TEXT, branch TEXT NOT NULL, worktree TEXT, git_dir TEXT, admission TEXT, state TEXT NOT NULL, stage TEXT NOT NULL, generation INTEGER NOT NULL, owner_id TEXT, owner_pid INTEGER, cancel_requested INTEGER NOT NULL, created_at TEXT NOT NULL, deadline_at TEXT, updated_at TEXT NOT NULL, reworks TEXT NOT NULL, process_count INTEGER NOT NULL, component_keys TEXT NOT NULL, input_sha256 TEXT, manifest TEXT, reason TEXT, limits TEXT NOT NULL, UNIQUE(repository,issue));
CREATE TABLE attempts(attempt_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, generation INTEGER NOT NULL, stage TEXT NOT NULL, role TEXT NOT NULL, instance_id TEXT NOT NULL UNIQUE, owner_id TEXT NOT NULL, input_sha256 TEXT NOT NULL, check_id TEXT, check_sha256 TEXT, state TEXT NOT NULL, launch_intent TEXT NOT NULL, evidence TEXT, result_sha256 TEXT, artifacts TEXT NOT NULL, created_at TEXT NOT NULL, finished_at TEXT);
CREATE TABLE verdicts(receipt_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, stage TEXT NOT NULL, generation INTEGER NOT NULL, input_sha256 TEXT NOT NULL, executor_instance_id TEXT NOT NULL, reviewer_instance_id TEXT NOT NULL, decision TEXT NOT NULL, return_stage TEXT, receipt_sha256 TEXT NOT NULL, body TEXT NOT NULL, superseded INTEGER NOT NULL);
CREATE TABLE effects(effect_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, ordinal INTEGER NOT NULL, kind TEXT NOT NULL, owner_id TEXT NOT NULL, intent_sha256 TEXT NOT NULL, intent TEXT NOT NULL, status TEXT NOT NULL, observation_sha256 TEXT, observation TEXT, UNIQUE(run_id,ordinal));
CREATE TABLE events(sequence INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL, kind TEXT NOT NULL, reason TEXT, old_state TEXT, new_state TEXT, attempt_id TEXT, effect_id TEXT, receipt_id TEXT, old_owner_id TEXT, new_owner_id TEXT, target_stage TEXT, generation_floor INTEGER, timestamp TEXT NOT NULL);
CREATE TABLE controller(singleton INTEGER PRIMARY KEY CHECK(singleton=1), owner_id TEXT NOT NULL, owner_pid INTEGER, started_at TEXT NOT NULL, last_tick_at TEXT NOT NULL, policy_sha256 TEXT NOT NULL, health TEXT NOT NULL);
```

The existing _pinned_database/_existing_database/_assert_existing/_recover_existing methods are private composition, not a public PinnedDatabase class. Preserve readonly noninheritable OS identity pins, single-link/path/FD identity checks, existing-only mode=rw and no initialization. Existing-only recovery remains exceptional shutdown behavior after positive contained-host cleanup; ordinary readonly failure stays failure. Shutdown shares its4.8s deadline across host and DB cleanup and keeps controller release behind proof. Preserve Windows capability guards before native side effects and portable status/cancel/inspect. ACTIVE is a legacy stage set, not future group capacity accounting.

## Concrete accepted signatures

The following are parsed from actual M; duplicate run_command definitions are shown because only the later definition is effective.

```text
pipeline_journal.py:105 PipelineJournal.__init__(self, path: Path, *, checkouts=(), forbidden_paths=())
pipeline_journal.py:109 PipelineJournal.operation_deadline(self, deadline)
pipeline_journal.py:122 PipelineJournal._pinned_database(self)
pipeline_journal.py:147 PipelineJournal._existing_database(self, identity)
pipeline_journal.py:154 PipelineJournal._assert_existing(self)
pipeline_journal.py:179 PipelineJournal._db(self, write=False, *, initialize=True)
pipeline_journal.py:354 PipelineJournal.submit(self, request: dict, policy: dict)
pipeline_journal.py:400 PipelineJournal.owner(self, owner_id)
pipeline_journal.py:428 PipelineJournal.claim(self, owner_id: str, max_active: int, *, queued_order=None)
pipeline_journal.py:501 PipelineJournal.record(self, run_id: str, owner_id: str, expected: dict, transition: dict)
pipeline_journal.py:606 PipelineJournal.begin_attempt(self, run_id: str, owner_id: str, binding: dict)
pipeline_journal.py:628 PipelineJournal.finish_attempt(self, attempt_id: str, owner_id: str, evidence: dict)
pipeline_journal.py:659 PipelineJournal.save_verdict(self, run_id: str, owner_id: str, receipt: dict)
pipeline_journal.py:902 PipelineJournal.claim_controller(self, owner_id, policy_sha256)
pipeline_journal.py:923 PipelineJournal.release_controller(self, owner_id)
pipeline_journal.py:936 PipelineJournal.recover(self)
pipeline_journal.py:938 PipelineJournal._recover_existing(self)
pipeline.py:40 native_execution_supported()
pipeline.py:48 adapter(request, config, journal)
pipeline.py:87 _runtime(args)
pipeline.py:206 _action(config, journal)
pipeline.py:213 _dispatch(config, journal)
pipeline.py:266 work(config, journal)
pipeline.py:291 watch_tick(config, journal, *, dispatch_tick=dispatcher.tick)
pipeline.py:336 _shutdown(config, journal, state, *, cancel_runs=True)
pipeline.py:386 watch(config, journal)
pipeline.py:401 main(argv=None)
pipeline_policy.py:28 load_pipeline_config(path, connections, executor_config)
pipeline_policy.py:134 admission_authorized(config, task, snapshot)
pipeline_policy.py:149 _source_current(project, profile)
pipeline_policy.py:197 continuation_authorized(config, run, snapshot)
executor_profiles.py:11 profile_fingerprint(profile)
executor_profiles.py:17 child_environment(environ)
executor_profiles.py:68 load_executor_config(path, connections)
executor_harness.py:6 build_invocation(attempt, profile)
executor_harness.py:36 capabilities(profile)
executor_harness.py:45 build_role_invocation(attempt: dict, profile: dict, *, role: str)
executor_harness.py:53 role_result_schema(binding: dict, *, reviewer: bool)
executor_harness.py:64 validate_role_result(path: Path, binding: dict, max_bytes: int=65536, *, reviewer: bool)
executor_worker.py:25 prepare_attempt(job, profile)
executor_worker.py:67 execute_one(config, queue, *, owner_id=None)
processes.py:25 run_command(argv, cwd, timeout_seconds, env=None)
processes.py:158 run_command(argv, cwd, timeout_seconds, env=None, *, cancel_requested=None, capture=None)
windows_job.py:67 WindowsJobProcess.__init__(self, argv, cwd, stdout, stderr, env=None)
pipeline_worker.py:163 _prepare(config, run, journal, owner)
pipeline_worker.py:199 _binding(run, role)
pipeline_worker.py:234 apply_verdict(config: dict, run: dict, binding: dict, result: dict, journal, owner_id: str)
pipeline_worker.py:465 step(config: dict, journal, *, owner_id: str | None=None)
pipeline_roles.py:88 _process(argv, cwd, timeout, env, directory, paths, config, profile, journal, run)
pipeline_roles.py:187 run_role(config: dict, run: dict, binding: dict, role: str, journal, owner_id: str)
pipeline_roles.py:277 run_checks(config: dict, run: dict, checkpoint: dict, journal, owner_id: str)
pipeline_publish.py:228 publish_one(config: dict, run: dict, journal, owner_id: str, *, store_factory=GitHubTasks)
```

## Issue18 Task3A handoff

Current R4 Windows-scope documents retain the accepted R3 typed legacy-fence correction and the exact17-table additive proposal. The actual original6-table digest matches the proposal and candidate preflight. No unanticipated accepted-M signature or SQL drift was found. The older runtime/groups18-task3-contract-map.md targets D5/fixed-capacity and remains historical, not an authority for current DDL.

Before implementation, append a binding-only accepted-M handoff to the current18 spec/plan: exactM/receipt above,6-table catalog/digest, actual private pin/noncreating/recovery signatures, real test entrypoints, and the migration boundary. Obtain fresh affected-document review because their bytes change. This audit identifies no new semantic amendment needed to R3/R4; do not reinterpret legacy origins or simplify unknown leases. Task3A may implement only the already specified explicit inspect/apply additive migration, private bounded backup, exact schema/version recognition, stopped owner/controller requirements, original-row/sequence preservation, typed legacy_fence provenance and safe reopen. Runtime group execution remains unavailable until its later accepted consumers exist. No source admission/backend redirection, G/epoch fabrication or legacy model execution follows from migration.

Existing real regression modules on M: tests/test_pipeline_journal.py, tests/test_pipeline_shutdown_recovery.py, tests/test_pipeline_cli.py, tests/test_pipeline_platform.py, tests/test_pipeline_scheduling.py, tests/test_pipeline_watch.py, tests/test_pipeline_worker.py, tests/test_pipeline_inputs.py, tests/test_pipeline_roles.py, tests/test_pipeline_publish.py, tests/test_pipeline_policy.py, tests/test_dispatcher.py, tests/test_dispatch_delivery.py, tests/test_dispatch_selection.py. New tests/test_group_migration.py is planned, not shipped. Task3A must freeze and test actual six-table SQL and old sequence rows, foreign/newer/corrupt no-write refusal, no-directory inspect, alias/hardlink/sidecar identity, bounded no-clobber backup/crash rollback, unknown legacy debt, unchanged committed backend/delivery and old-binary refusal of v2. Native resource collectors/group pilots stay Windows-qualified; POSIX61 remains deferred.

## Issue21 Task1 handoff

Actual build_invocation branches custom and otherwise falls through to Codex; build_role_invocation validates role, custom delegates, otherwise uses the generic builder and Codex sandbox adjustment. Missing kind currently raises KeyError, not a deliberate unsupported-kind ValueError. load_executor_config currently admits codex/custom only. load_pipeline_config has no independent explicit kind matrix and relies on common-loader closure. Expanding common loader without closing these consumers would admit a new wrong-kind path.

Concrete affected production paths: executor_harness.build_invocation and build_role_invocation; executor_worker.execute_one; pipeline_policy.load_pipeline_config/admission_authorized/continuation_authorized; pipeline_worker.step/_prepare; pipeline_roles.run_role/run_checks/_process. Role builder signature above is keyword-only role. There is no pipeline-specific alternative role builder. The actual pipeline's six role names are spec_executor, spec_reviewer, development_executor, development_reviewer, test_executor, test_reviewer; OpenCode foreground qualification grants none of them. Add independent closed validation before preparation/probe/child and direct generic/role ValueError guards preserving all accepted codex/custom argv. Unknown/missing/nonstring kind must fail closed; never simply fall through to Codex.

Existing concrete tests: tests/test_executor_profiles.py, tests/test_executor_harness.py, tests/test_executor_worker.py, tests/test_executor_processes.py, tests/test_processes.py, tests/test_pipeline_policy.py, tests/test_pipeline_roles.py, tests/test_pipeline_worker.py, tests/test_pipeline_cli.py, tests/test_pipeline_platform.py. New opencode_adapter/discovery/runner modules and tests are future Task1/2 code. Update the21 plan's accepted-base block and Task1 affected-files/entrypoints with these actual names/signatures, then obtain fresh affected-document review before coding. No semantic drift requires a different policy than acceptedR4; this is the explicitly required concrete ABI binding.

The effective process runner has only cancel_requested/capture optional keywords; no stdin_spec or scope exists. WindowsJobProcess opens DEVNULL internally and has no stdin parameter. stdin_spec={path,expected_sha256,expected_bytes,expected_identity}, anonymous readonly staging,4MiB instruction bound and64MiB complete EOF capture remain future Task2 changes requiring TDD/review; do not call them as if acceptedM already implemented them. Preserve legacy call/result/containment semantics. Full60 means60 source instruction files, not60 seconds. Pinned OpenCode source/policy/qualification/discovery still applies; no native probe, install/auth/model change or claim of an available local CLI is authorized by this audit. Native POSIX62 and Claude20 stay deferred.

## Other boundaries

Issue17 Task3 can consume this exact accepted source identity but still needs its own actual publication freshness/effect/journal-CAS audit. It gains no repository writer/protection attestation or additional close authority from this report. Product63's uncommitted fetch timeout change is not part of M: actual M tasks._git has no timeout keyword and uses10s; a future merged63 changes only this local-helper signature and postmerge fetch budget, not the six-table schema or the execution APIs above. Re-audit actual new main when it lands.

## Current downstream document bindings

The current files below were read, not edited or accepted by this audit.

| File | Raw SHA256 | Canonical SHA256 |
| --- | --- | --- |
| task-tower-capture/docs/superpowers/specs/2026-11-02-agent-groups-design.md | c488845f3fcd2cf446f820452c7c2dd1b22d2cae6fbd257bb3813e7b8aeae867 | 198a1c180e3c019482e2f47175de5bb60bcc6a9c9255de2597e204ee0fc94647 |
| task-tower-capture/docs/superpowers/plans/2026-11-02-agent-groups.md | cf8e7a6946c5a1c5fcf0869ed9b9a7f211212c62fd63d0422782638d7a28530a | ccc929d681322a3f9d96f006b14a3eabd541ec010f01d1fdb3eb1812fcaf72e1 |
| task-tower-opencode/docs/superpowers/specs/2026-11-02-opencode-adapter-design.md | aafe165c23182656f85fe272b8fa2ee0fd03a73627fb7e515bf6fa18cf93c03b | 3c7987e1972b28026ec8a6d5768e934baaa823c1ff6493169c92e276e75fe018 |
| task-tower-opencode/docs/superpowers/plans/2026-11-02-opencode-adapter.md | 31369e1af8988d13fe97a20eeac5ef03723ae210d340a0b01b9521c94994a813 | 605528f322857405675780f373036acdfc15ab0c117a655da30c9032d1b3f420 |
