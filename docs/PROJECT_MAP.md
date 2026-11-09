# Task Tower: connector and diagnostic map

Verified 2026-11-09 against the working changes on
`codex/preparing-preflight-20261109`, based on accepted
`48c01987ceb4bb67ca2f09e3a30d9bd280ab0f2f`. This is a source map, not a claim
that the changed code is deployed or that a historical failure is resolved.

| Boundary | Source and responsibility |
| --- | --- |
| Operator entry | [connector CLI](../task_tower/connector/cli.py): explicit ready/import/adopt/decision commands and read-only inspect |
| Managed execution | [client](../task_tower/connector/client.py): fixed lifecycle commands and stage-bound failure recording |
| Git source | [worktrees](../task_tower/connector/worktrees.py): exact-source/clean-worktree checks and bounded Git operations |
| Transport state | [store](../task_tower/connector/store.py): owned journal, ordered events and unknown-effect fences |
| Safe inspection | [diagnostics](../task_tower/connector/diagnostics.py): typed receipts, private raw evidence and read-only snapshots |
| Preparing contract | [receipt/source](../task_tower/preparing_recovery.py): exact operator-digest binding and fixed clean engine identity, rejecting index flags that hide source changes. This library component enables no recovery route. |
| Preparing preflight | [worktrees](../task_tower/connector/worktrees.py): read-only command, preparing intent and bounded Git observations; no attach, resume or fence release. |

The operator command and its limits are in
[connector diagnostics](runtime/connector-diagnostics.md). Core verification:
`python -m unittest discover -s tests -v`; focused diagnostic contracts:
`python -m unittest tests.test_connector_diagnostics -v`. Run final checks through
Reslop as required by the working agreements and retain raw evidence locally.
Preparing contract/preflight checks: `python -m unittest tests.test_preparing_recovery tests.test_preparing_preflight -v`.

Beads remains the canonical task/owner/dependency/history engine. See
[current direction](current-direction.md) and [project intake](project-intake.md).
Inspection neither launches a worker nor authorizes recovery or delivery.
