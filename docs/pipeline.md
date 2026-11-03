# Local stage pipeline operations

The pipeline turns an explicitly authorized delivery into independently accepted specification, development and test stages, then an optional reviewable PR. It uses a private installation policy and journal, six fresh executor/reviewer role instances, fixed host checks and durable Git/publication intents. Public Markdown is an evidence projection; model output, Issue prose and editable cards do not grant authority.

This guide describes the bounded local stage pipeline; task completion additionally requires independent PR/main acceptance and verified Issue publication. The first installed Codex pilot ran two fresh roles, then parked on a rejected specification at its zero-rework limit. The preserved UTF-8 source and reviewer shell rendering differed; the exact-shell diagnostic reproduced stdout encoding loss. See the [independent negative-pilot audit](tasks/evidence/TT-PIPELINE-001/installed-codex-blocked-review.md). ASCII-escaped UTF-8 source-reading guidance has its own independent review; a distinct third pilot subsequently completed the six-role ready boundary described below. Fixture tests, an installed executor scratch smoke and this guide do not establish unattended readiness. Issue17 owns PR acceptance/merge and the main/postmerge/Issue-closure barrier; this pipeline never merges or closes an Issue.

## Private setup

Use an existing authenticated host, native Python3.11+, installed Codex or explicitly trusted custom executable, pinned Superpowers instructions and explicit repository-linked connections. Follow [executor profile setup](executor.md) and [project-first setup](github-setup.md). No tool installation, model selection, credential scope grant or OS service is performed here.

All CLI inputs, request/results and journals must be absolute private paths outside every connected checkout, mutually distinct including SQLite sidecars. Reject symlink/junction/hardlink aliases. A pipeline journal is separate from executor/dispatcher databases; never repoint an existing delivery backend or copy a journal to claim ownership elsewhere. Private policy contains no tokens. Preserve existing Git transport authentication separately.

For the example below, existing connections and executor settings must bind exactly:

- Connection repository `owner/repo`, runner_label `local`, checkout `C:/TaskTower/repos/repo`, and trusted_publishers containing `operator`.
- Executor profile `local-codex` for that same repository/checkout/runner, with its approved absolute executable, source_ref, private runs_dir, limits and validated Superpowers pins.
- Executor allowlist row `{ "repository":"owner/repo", "issue":16, "task_id":"TT-PIPELINE-001", "runner_label":"local", "profile":"local-codex" }`.

Replace example identities and paths with explicitly authorized existing values. They are illustrative, not new authorization or files to commit. Profile pins/check executable must validate on that host. Even when publishing is disabled, publisher_account must match trusted_publishers; it cannot be omitted.

`C:/TaskTower/private/pipeline.json` contains every required task field:

```json
{
  "version": 1,
  "max_active": 2,
  "interval_seconds": 5,
  "task_timeout_seconds": 7200,
  "role_timeout_seconds": 900,
  "max_reworks": 2,
  "max_processes": 36,
  "log_max_bytes": 1048576,
  "tasks": [{
    "repository": "owner/repo",
    "issue": 16,
    "task_id": "TT-PIPELINE-001",
    "runner_label": "local",
    "executor_profile": "local-codex",
    "components": ["core"],
    "allowed_paths": ["src/", "tests/", "docs/"],
    "spec_path": "docs/spec.md",
    "plan_path": "docs/plan.md",
    "evidence_dir": "docs/evidence/",
    "checks": [{
      "id": "unit",
      "argv": ["C:/Python311/python.exe", "-m", "unittest", "discover", "-s", "tests", "-v"],
      "timeout_seconds": 300
    }],
    "ci_substitution": {"enabled": false, "required_platforms": []},
    "publish": {"enabled": false, "remote": "origin", "base_ref": "refs/heads/main", "publisher_account": "operator"}
  }]
}
```

Task rows have exactly those fields; unknown keys, duplicate/foreign Issue/task mappings and Boolean numeric limits fail validation. components is a nonempty unique list of installation-owned names; `['*']` is the conservative exclusive declaration for uncertain ownership. allowed_paths are nonoverlapping safe relative POSIX file paths or directory prefixes ending `/`. Spec/plan must be distinct files within them; evidence_dir must end `/`, be allowed and contain neither spec nor plan. Reject traversal, `.git`, Windows aliases/reserved names and unsafe separators. Role changes outside allowed paths cannot be published.

checks is nonempty, with unique IDs, approved absolute native argv[0] and integer timeout1..3600; argv comes only from private installation policy, never model/Issue text. `.cmd`/`.bat` cannot be argv[0]. ci_substitution is either disabled with [] or enabled with a unique nonempty subset of `windows`, `macos`, `linux`. An actual configured-check failure is never erased by CI substitution. publish requires exactly enabled, origin, refs/heads/main and the trusted publisher identity. Enabling it is explicit permission to push the dedicated accepted branch and create/adopt its strictly bound PR, not to merge or close anything.

| Optional top-level limit | Default | Inclusive range |
| --- | --- | --- |
| max_active |2|1..2|
| interval_seconds |5|1..60|
| task_timeout_seconds |7200|1..86400|
| role_timeout_seconds |900|1..3600|
| max_reworks |2|0..5 per target stage|
| max_processes |36|6..100|
| log_max_bytes |1048576|1..67108864|

Roles/checks use the minimum applicable configured timeout, role limit, executor-profile limit and remaining task budget; capture uses the lower pipeline/profile byte limit. The durable task budget begins at first claim and includes preparation/checkpoints/publication. Restart does not renew it; live elapsed time is monotonic and clock rollback fails closed. Process count includes managed roles and configured checks; fixed host helpers are separately contained/bounded. These are time/process/storage limits, not a dollar/token budget.

## Genuine dispatcher binding

watch uses the existing genuine dispatcher selection and verified_done dependency proof. Closed Issues, status labels, library declarations and model claims do not satisfy dependencies. The dispatcher allowlist must be a subset of the same pipeline task identities. Its backend must exactly match the fixed adapter invocation generated for this installation, including normalized absolute Python, paths, argument order and repository-root cwd. Committed backend fingerprints cannot be silently replaced.

Example `C:/TaskTower/private/dispatch.json`, assuming the running pipeline uses exactly this Python/path layout:

```json
{
  "version": 1,
  "interval_seconds": 5,
  "allowlist": [{"repository":"owner/repo","issue":16,"task_id":"TT-PIPELINE-001"}],
  "backend": {
    "argv": ["C:/Python311/python.exe", "-m", "task_tower", "pipeline", "adapter",
      "--connections", "C:\\TaskTower\\private\\connections.json",
      "--config", "C:\\TaskTower\\private\\pipeline.json",
      "--executor-config", "C:\\TaskTower\\private\\executor.json",
      "--journal", "C:\\TaskTower\\private\\pipeline.sqlite3",
      "--request", "{request}", "--result", "{result}"],
    "cwd": "C:/TaskTower/task-tower",
    "timeout_seconds": 30
  }
}
```

Use the resolved path of the Python actually starting watch (the built-in host invocation uses sys.executable), not an alias or a different interpreter. On Windows, private path argument strings must use the native backslash spelling shown in the JSON (escaped as `\\`); slash aliases are not exact backend identity matches. Backend argv order is an identity requirement even though the command-line parser accepts reordered flags. Dispatcher interval_seconds has its existing5..3600 range; pipeline's own interval controls normal watch refresh scheduling. Proven pre-intent source read failures back off5/10/20/40/60seconds, resetting after success. A committed delivery intent is lookup-only; transport error/absence is never permission to resubmit it.

## Commands and stopping

Run from the canonical repository root with the existing approved Python. PowerShell variables below are path placeholders, not environment secrets:

```powershell
$python = 'C:/Python311/python.exe'
$connections = 'C:/TaskTower/private/connections.json'
$pipelineConfig = 'C:/TaskTower/private/pipeline.json'
$executorConfig = 'C:/TaskTower/private/executor.json'
$pipelineJournal = 'C:/TaskTower/private/pipeline.sqlite3'
$dispatchConfig = 'C:/TaskTower/private/dispatch.json'
$dispatchJournal = 'C:/TaskTower/private/dispatch.sqlite3'
$common = @('--connections', $connections, '--journal', $pipelineJournal)

& $python -m task_tower pipeline adapter @common --config $pipelineConfig --executor-config $executorConfig --request 'C:/TaskTower/private/request.json' --result 'C:/TaskTower/private/result.json'
& $python -m task_tower pipeline work @common --config $pipelineConfig --executor-config $executorConfig --once
& $python -m task_tower pipeline watch @common --config $pipelineConfig --executor-config $executorConfig --dispatch-config $dispatchConfig --dispatch-journal $dispatchJournal
& $python -m task_tower pipeline status @common
& $python -m task_tower pipeline status @common --run-id 'RUN_UUID'
& $python -m task_tower pipeline cancel @common --run-id 'RUN_UUID'
& $python -m task_tower pipeline reconcile @common --run-id 'RUN_UUID' --inspect
```

Adapter v1 request has exactly operation (`submit` or `lookup`), delivery_id UUID, repository, Issue integer, task_id and runner_label, for example `{"operation":"submit","delivery_id":"11111111-1111-4111-8111-111111111111","repository":"owner/repo","issue":16,"task_id":"TT-PIPELINE-001","runner_label":"local"}`. The result file carries the strict durable admission receipt; accepted admission is not accepted development. watch normally supplies requests through its bound dispatcher rather than manual delivery creation.

work --once performs at most one role, check batch, checkpoint or publication action. watch repeatedly admits and refills without chat prompts while its host process runs. One journal controller owns watch; atomic worker claims remain authoritative for concurrent work processes. Ctrl-C requests contained child termination before DB reconciliation, with one shared shutdown budget of at most5seconds. Unconfirmed cleanup/SQLite lock/ownership records uncertainty and retains reservations; never report success merely because the UI/parent stopped. status, cancel and reconcile --inspect need connections/journal, not executable pins/config, and remain available after profile revocation. cancel does not prove rollback or completion; inspect is read-only and cannot reset or replay unknown effects.

Current native pipeline execution is Windows-qualified and uses Job Objects. On other platforms work/watch and internal action/dispatch helpers return unsupported_platform before runtime initialization or child launch. Adapter/status/cancel/reconcile --inspect remain portable; cancel records intent without claiming cleanup. Linux/macOS nested process containment and native acceptance are deferred to [Issues59/60](platform-support.md). Existing portable CLI behavior and applicable three-platform CI remain mandatory. No service installation or authentication changes are implied.

Exit0 means a valid bounded admission/status/tick, including an explicitly parked needs_input/cancelled/timed_out result. Exit1 means work operational unavailability/uncertainty or unconfirmed watch shutdown; inspect JSON even when exit0. A no-run `unavailable` result has reason `source_unavailable` and null run/stage/generation/digests: it creates no journal run state or execution claim. Internal fixed host transport may complete with exit0 while public work reports this unavailable result with exit1. Adapter exit0 means its strict wire exchange completed, possibly with unknown/not_found; read the result rather than inferring admission. Exit2 means invalid/unavailable private state, policy or arguments. Public JSON contains neutral statuses/reasons, qualified identities, counters/timestamps and hashes/allowed PR URLs, never private paths, argv, prompts, raw logs, model summaries or tokens. `_action` and `_dispatch` are fixed internal host transports, not operator-selected executors.

## Ownership, stages and recovery

Specification executor/reviewer, development executor/reviewer and test executor/reviewer are fresh distinct instances. Strict v2 results bind current run/attempt/instance, generation, source/checkpoint/input hashes and required artifacts; genuine host launch/cleanup, checkpoint and configured-check evidence gate advancement. Executors never approve their own output. Host-created Markdown and task cards project journal evidence; editing them cannot create a receipt. Stale or rejected inputs invalidate affected downstream receipts and consume bounded target-stage rework. max_reworks2 allows the initial attempt plus two returns per stage. needs_input is visible parked work; unknown launch/process/effect is fenced and never automatically reworked.

Two local slots support simultaneous actions across **different repositories**. Linked worktrees share refs: same-repository preparation, roles, checks, checkpoints and publishing are atomically serialized, including public work --once. Ready continuations take precedence; otherwise fresh genuine host eligibility orders queued work by P0/P1/P2/P3, repository and Issue (absent priority defaults to P3). Priorities and ordering hints never grant task permission; source selection happens outside the atomic journal claim. Newly arrived rows wait for a fresh selection pass. A known clean queued revocation becomes needs_input/policy_revoked without a process, owner, deadline or effect; criteria are first frozen at actual preparation, not identity delivery. Unavailable or partial dependency evidence instead leaves the run unclaimed and visible as source_unavailable. Healthy independent actions continue with a source warning when appropriate. Only unavailable queued reads back off5/10/20/40/60seconds; safe ready continuations bypass that queued backoff. Scheduling may finish one same-repository run before admitting another; no fairness or same-repository simultaneous-agent guarantee. Full Git-ref mutation guards remain intact. Unknown owners retain task/component slots and block replay in that repository. Positive dead-and-clean ready handoff requires saved completed evidence; death alone never frees unknown work.

There is no reset/retry-unknown/resume-by-journal-deletion command. Do not delete journals, forge Markdown receipts, force-push or change authorization to escape a fence. Preserve source, attempts/intents and inspection output for explicit owner reconciliation outside this milestone. Lost push/PR responses are unknown; read-only observation cannot justify a second write merely because nothing is found. With publish disabled, accepted work stops at ready_for_pr after local host evidence; enabled publication can end awaiting_pr, never Done.

Only fixed trusted host `_action`/`_dispatch` helpers may inherit existing GH_TOKEN/GITHUB_TOKEN for host API reads/writes, including environment-only installations, or use existing host authentication. Model/custom role and configured-check children strip these keys case-insensitively. Git child filtering remains separate. Never place credentials in argv, prompts, config, result/log artifacts or public reports. Worktrees and token-variable stripping are not OS credential sandboxes for trusted custom programs.

The second installed pilot completed all six real roles, three independent approvals and its fixed host check, but parked at final checkpoint verification because Windows Git treated an ambiguous object/path argument as a long filesystem path. The dedicated blob-reader correction is independently accepted; read-only validation of that preserved checkpoint succeeds without changing its parked journal. See the [qualified v2 evidence audit](tasks/evidence/TT-PIPELINE-001/v2-evidence-review.md) and [blob-reader review](tasks/evidence/TT-PIPELINE-001/host-blob-read-review.md). A fresh third pilot subsequently reached ready_for_pr; the original parked journal remains unchanged.

The third pilot used six fresh installed Codex instances and three current approval receipts. It reached ready_for_pr after a configured check and final evidence-only checkpoint, with seven cleaned attempts and no unresolved effect. The [independent installed-pilot audit](tasks/evidence/TT-PIPELINE-001/installed-codex-smoke-review.md) binds source8981c6d and443 frozen files. GitHub transport was a fixture using production readers; publishing was disabled. This proves neither live GitHub deployment nor service/night operation. Later checkpoint-authority, scheduling/source handling and SQLite-sidecar corrections lie outside that model-pilot source and require their own current regressions and independent acceptance. Original parked runs, rejected reports and the unproven cause of the original macOS CI failure remain preserved.

A user may start watch through an existing supervisor; this change installs no service/startup task. Local SQLite/PID ownership is not a cross-host lock. Issue18 owns broader groups/capacity/fair scheduling, Issue19 distributed ownership, and Issue17 integration through exact-main/postmerge/automatic closure. The qualified installed pilot is accepted only at source8981c6d; every release additionally requires current whole-branch/CI and exact-main acceptance.

## Explicit group registration (bounded Task3BRa)

After independent review of the installation inputs and an explicitly chosen cold storage migration, the host registration command is:

```text
python -m task_tower.pipeline register-groups --connections C --config P --executor-config E --journal J --groups-config G --apply
```

This changes the existing private installation journal. Do not run it implicitly during setup or against a live installation. Actual private inputs must be valid and owners/controllers stopped; registration/adoption and epoch updates are atomic and never manufacture old process facts. Missing/foreign/hot storage remains refused. Metadata status and discovery stay read-only. Registered work/watch execution remains unavailable until the later pure-wire/resource/workspace gates; registration does not lift v1's two-slot limit or qualify unattended operation. See [bounded acceptance](tasks/evidence/TT-GROUPS-001/task3bra-acceptance.md). Original hot recovery remains Issue65.
