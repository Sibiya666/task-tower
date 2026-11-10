# Connector failure inspection

Use the installed project source and its known operator config:

```console
python -m task_tower.connector.cli inspect <known-attempt-id> --config <private-connector-config>
```

This command reads only the configured connector transport journal. It does not
read the API credential, contact a model/API, start a service, construct a
ConnectorStore, recover a command, acknowledge an event or modify task ownership.
It uses SQLite `mode=ro`, `query_only` and one bounded read transaction. The
connector identity, schema, project scope and journal file identity must match.
Missing/linked/foreign/malformed journals fail closed; no database is created.
The SQL read has a two-second budget, a 32-command limit and a 1 MiB JSON budget.

Exit 0 returns versioned JSON containing safe command phases, registration
booleans, worktree state/base, that attempt's pending outbox count and any saved
failure receipt.
Exit 4 with `inspection_unavailable` means the read could not be verified; it is
not evidence that a command, task, process or external effect is absent. Invalid
operator configuration retains the existing exit 2 boundary. No prompts, argv,
private paths or exception strings appear in the inspection output.

New lifecycle failures preserve a typed stage and an allowlisted reason together
with the existing failed event. Git failures additionally record bounded exit,
cleanup and truncation facts. Disk-full, permission and branch-exists reasons are
derived from that failing command's captured stderr, never guessed from later
state. A failed or unknown `turn_start` is still unknown execution.

Git capture is created privately and verified before the Git process can write
raw output. Windows creation uses an exclusive new directory with a protected
DACL for the current user, SYSTEM and administrators; existing ACLs are untouched.
An unverifiable capture directory stops the operation before Git starts.
Owner/DACL verification runs in-process through Win32 APIs within the existing
Git budget, so each Git operation does not launch a verifier subprocess.

When possible, captured Git stdout/stderr prefixes are retained privately under
`task-tower-git-failure-<id>` in that worker's established temporary directory.
The receipt identifies the local artifact and SHA256 of each captured prefix;
it never exports its absolute path. Failure to retain raw evidence is explicit.
Truncation/unknown tails remain unknown; these hashes do not prove full output.
Keep artifacts local and outside commits, and use only the known worker temp
binding to locate one. Do not scan private directories to find a missing binding
or publish operational artifact identifiers in GitHub comments.

Older failures have no typed receipt. `failure_receipt: null` means unavailable
historical detail, not a successful operation or an inferred failure reason.
Inspection does not make `needs_reconciliation` resumable. Preserve claims,
capacity and unknown-outcome fences until a separately authorized supported
reconciliation procedure applies. This change adds no recovery operation.

The internal `Worktrees.inspect_preparing` library verifies a known pre-executor
preparing intent and bounded Git observations without mutation. It is not a CLI
recovery command, does not release fences, and does not support old author or
committed handoffs. Explicit operator approval and a separate supported recovery
procedure remain necessary before any attach or execution.

The internal transport store also persists typed preparing-operation intents.
Each receipt and attempt is reserved once; restart retains pending/unknown
intents without replay. A known result, supplied ready-worktree record and
one safe acknowledgement commit together, only if the original command,
worktree and attempt-scoped pending-event snapshot still match. Failure
between writes rolls back all three records. Existing claims and command
fences remain unchanged. This storage primitive does not validate Git,
authorize attach or start execution; those require a separate approved runner.
Disposable SQLite tests verify storage behavior, not actual Git delivery.

The separate internal `PreparingRecovery` runner requires an explicitly approved
receipt digest and actual fixed engine source before observations or intent.
It keeps the read-only preflight and journal reservation under the same lock,
then attaches only the known existing branch, without branch creation, force,
reset, prune or remote guessing. A shared bounded Git deadline covers attach and
exact clean target/base/branch/common-repository readback before atomic storage.
Known duplicates read the saved result; unknown intent, Git or cleanup outcomes
never replay. The original command remains fenced. This library is not a CLI
recovery admission route and starts no model. Live reconciliation still needs
a separate exact operator approval and the later supported service bridge.

Internal service preparing admission/status uses a bounded, default-empty constructor
approval registry. It verifies exact receipt/source history and fresh native
owner/profile/task/dependencies, rejects decisions/additional commands, and reserves
one deterministic control on the same unknown/fenced attempt, owner and capacity.
Ordinary execute/resume gates remain. This adds no HTTP/config admission, prepared
acknowledgement, control execution or live recovery; later approved parts are needed.
