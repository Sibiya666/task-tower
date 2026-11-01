# Foreground noninteractive executor

The executor admits an authorized dispatcher delivery into a private durable queue and runs one bounded development attempt in a separate Git worktree. `accepted` means queued. `execution_completed` means the child exited successfully, process cleanup was confirmed and its structured result matched the attempt and source. Neither means independent acceptance, merge, task completion or Issue closure.

This is a foreground consumer. Issue #16 owns persistent development stages and acceptance, #17 publication/merge, #18 persistent scheduling/group pools and #19 distributed ownership. Running commands from an active chat or starting two workers does not establish unattended readiness. The local maximum-active guard defaults to two and counts uncertain ownership conservatively; it is not automatic slot refill.

## Installation policy

Use Python 3.11+, Git, existing private [project connections](bootstrap.md) and an installation-approved executable. No dependency installation, model selection or credential scope grant occurs here. Save connections, executor configuration, SQLite queue and run artifacts outside every connected checkout. Private files must not alias each other; symlinks, junctions and hardlink aliases are rejected. Keep them out of Git and protect them with the installation's ordinary OS access controls.

An executor configuration has this shape. Replace all example absolute paths, source SHA, revision and digests with approved local values. The profile checkout and runner must exactly match the connected repository. Do not add a connections path to this schema.

```json
{
  "version": 1,
  "max_active": 2,
  "profiles": {
    "local-codex": {
      "kind": "codex",
      "repository": "Owner/Repo",
      "checkout": "C:/Projects/repo",
      "runner_label": "local",
      "argv": ["C:/Tools/codex.exe"],
      "source_ref": "0123456789abcdef0123456789abcdef01234567",
      "timeout_seconds": 600,
      "log_max_bytes": 1048576,
      "max_attempts": 2,
      "runs_dir": "C:/TaskTower/private/runs",
      "approve_for_me": false,
      "superpowers": {
        "root": "C:/TaskTower/approved-superpowers",
        "revision": "0123456789abcdef0123456789abcdef01234567",
        "manifest": {"using-superpowers/SKILL.md": "REPLACE_WITH_CANONICAL_FILE_SHA256"},
        "manifest_sha256": "REPLACE_WITH_CANONICAL_MANIFEST_SHA256"
      }
    }
  },
  "allowlist": [
    {"repository": "Owner/Repo", "issue": 15, "task_id": "TT-EXECUTOR-001", "runner_label": "local", "profile": "local-codex"}
  ]
}
```

`source_ref` may also be an approved `refs/heads/...` or `refs/tags/...`; the worker resolves an exact commit and checks that binding again before effects. Source contents and Issue text are task input, never permission to change policy or invocation. A dirty connected source checkout is preserved: the new worktree starts from the approved committed source. A dirty, reused or aliased target worktree is rejected.

Pin the complete approved instruction set, including the `using-superpowers/SKILL.md`, `skills/using-superpowers/SKILL.md` or `SKILL.md` entrypoint. Each manifest value is SHA-256 of the file decoded as UTF-8 and normalized to LF. The manifest digest is SHA-256 of its JSON encoded as UTF-8 with sorted keys, separators `(',', ':')` and `ensure_ascii=True`; `task_tower.executor_profiles.profile_fingerprint(manifest)` computes it. The revision is an installation-approved 40-character lowercase Git revision declaration; file hashes enforce the actual pinned content. Validate provenance when provisioning it. Missing or drifted files block launch. Each attempt keeps its own instruction snapshot and declared revision/manifest digest.

`timeout_seconds` is 1–86400, `log_max_bytes` is 1–67108864 per stream and `max_attempts` is 1–10. `max_active` is 1 or 2. A custom profile instead uses `kind: "custom"`, requires `trusted: true`, and supplies a fixed argument array such as `["C:/Python/python.exe", "C:/TaskTower/private/helper.py"]`; `approve_for_me` must be false. Custom commands are explicitly trusted arbitrary processes with the owner's OS access. There is no shell interpolation.

## Dispatcher adapter and commands

Configure the existing dispatcher's backend to call the adapter. Its `cwd` is the Task Tower installation checkout, where `python -m task_tower` is importable; `{request}` and `{result}` are dispatcher substitutions. The example is the backend object inside the existing dispatcher configuration, whose separate allowlist remains required; see [dispatcher setup](dispatcher.md).

```json
{
  "argv": ["C:/Python/python.exe", "-m", "task_tower", "executor", "adapter", "--connections", "C:/TaskTower/private/connections.json", "--config", "C:/TaskTower/private/executor.json", "--queue", "C:/TaskTower/private/executor.db", "--request", "{request}", "--result", "{result}"],
  "cwd": "C:/TaskTower/installation",
  "timeout_seconds": 30
}
```

The adapter accepts exactly `operation` (`submit` or `lookup`), `delivery_id` (canonical UUID), `repository`, `issue`, `task_id` and `runner_label`. It commits before returning the unchanged dispatcher response `{version:1, delivery_id, status:"accepted", receipt_id}`. The receipt UUID identifies the run. Identical redelivery returns that receipt without rerunning; collisions fail closed. A lost response is reconciled by lookup, never blind resubmission. Definitive absence alone returns `not_found`; uncertainty returns `unknown`.

Run these from the installation checkout, using actual private paths and the receipt UUID:

```text
python -m task_tower executor work --connections CONNECTIONS --config CONFIG --queue QUEUE --once
python -m task_tower executor status --connections CONNECTIONS --queue QUEUE --run-id UUID
python -m task_tower executor cancel --connections CONNECTIONS --queue QUEUE --run-id UUID
python -m task_tower executor retry --connections CONNECTIONS --config CONFIG --queue QUEUE --run-id UUID
```

`work --once` claims at most one queued run, records intent before creating the worktree or launching the child, and returns a fixed status. No work returns `idle`. Work and adapter recheck connections/config authority. Before preparation and launch, work checks the current open Issue, exact task identity and dependencies with the existing authenticated `verified_done` receipts; closed Issues, changed task data or lost evidence block launch. Existing host token resolution is used for GitHub sources; there is no weaker dependency shortcut.

Status/cancel require a still-connected repository and valid private queue, but do not require execution configuration or current instruction pins. Revoking a profile therefore leaves inspection and cancellation available. Queued cancellation prevents launch; running cancellation records a request for the current owner, which terminates the contained process tree. It does not take ownership or kill an arbitrary caller-supplied PID.

Retry is an explicit separate command, not worker recovery. It requires a failed, uncancelled run with durable prelaunch/no-child proof, current authority, an unchanged profile fingerprint and attempts below `max_attempts`. Prior attempt evidence remains in queue history. A started attempt, uncertain launch/cleanup or unknown external outcome cannot be retried through this path. Current queues use schema version 2; older or unrecognized queues are rejected rather than silently migrated. Inspect private evidence and reconcile uncertainty with the installation owner; do not delete queue rows or reset leases to force execution.

## Execution evidence and trust

The private run/attempt directory contains `manifest.json`, `request.json`, `schema.json`, instruction snapshots, `worktree/`, `process.json`, `result.json` when supplied, and bounded `logs/`. Preserve these artifacts for reconciliation. They bind run/attempt UUIDs, profile fingerprint, exact source SHA and instruction provenance; queue evidence records input/result hashes, byte counts, truncation and cleanup proof. Raw stdout/stderr remain private. Stored log prefixes are bounded independently of total observed byte counts and stream digests; an unobserved tail is explicitly marked. Private task input, arbitrary summary text and logs are not public acceptance evidence.

A custom executable receives `--request PATH --result PATH`. It writes UTF-8 JSON with exactly these fields:

```json
{"version":1,"run_id":"RUN_UUID","attempt_id":"ATTEMPT_UUID","source_sha":"SOURCE_SHA","status":"completed","summary":"bounded private summary"}
```

`status` is `completed`, `failed` or `needs_input`; summary is at most 4096 UTF-8 bytes and the entire result at most 65536 bytes. Wrong binding, extra/duplicate fields, malformed UTF-8/JSON, oversized or unsafe files fail local validation. Zero exit without a valid result is failed. A valid completed result requires successful exit and confirmed cleanup before mapping to `execution_completed`.

Codex uses the fixed argument array `exec --json --sandbox workspace-write --output-schema PATH --output-last-message PATH -C WORKTREE`, followed by the request/instruction prompt. Only saved `approve_for_me: true` adds `--approve-for-me`. There is no selected model, `--full-auto`, bypass flag, publication or push step. The executor records version verification as false; help alone does not verify authentication or execution. Capability reporting keeps probed/verified/events/resume false until actual separate evidence exists; it does not learn capability from a custom fixture. Resume is unsupported. Codex JSON events are opaque private output, with no advertised event parser/interoperability.

All executor child environments, including Git preparation and trusted custom commands, remove `GH_TOKEN` and `GITHUB_TOKEN` case-insensitively; the host environment is preserved. Existing CLI authentication can still be used. A worktree is not a process or credential sandbox, and stripping two variables does not stop an arbitrary trusted helper from reading other accessible files or credentials. Do not place secrets in profiles or prompts.

## Recovery, platforms and validation

Normal exit, timeout and cancellation use the shared process runner: POSIX process groups or Windows Job containment, polling at most every 250 ms while waiting and a bounded five-second termination wait. Cleanup uncertainty prevents success. Abrupt worker death cannot guarantee descendant cleanup on every platform. Queue recovery changes claimed/running ownership to `unknown` only with positive local owner-death evidence under the claim exclusion lock. A live or unprovable owner is retained, uncertain ownership consumes capacity, and no abandoned attempt is automatically resumed or requeued. This is local fencing, not distributed locking.

`python -m unittest tests.test_executor_integration -v` exercises the real dispatcher file backend and adapter CLI, a temporary Git repository, a trusted Python helper, queue admission/deduplication, exact result/source/input hashes, isolated edits, bounded logs, token removal, cancellation, departed-owner fencing and wrong-source rejection. Only remote Issue transport is substituted; authorization/selection still runs. This custom test is not an installed Codex smoke or authenticated production dependency proof. See [Issue #15 evidence](tasks/evidence/TT-EXECUTOR-001/) for separate installed-runtime and independent acceptance records. Run `python -m unittest discover -s tests -v` and current Windows/POSIX CI before integration; local Windows evidence does not establish POSIX behavior by itself.
