# GitHub project setup

Each connection owns its repository, Issues and optional GitHub Project. Product source does not store your connections. Use installation-private JSON outside every repository; never put tokens in JSON. Credentials resolve from GH_TOKEN/GITHUB_TOKEN or existing gh/git credentials.

## Supported execution

This release dispatches **postmerge independent acceptance only**. It does not implement development, merge automation or general Issue commands. A trusted mapping binds Issue numbers to committed `docs/tasks/TT-*.json` cards. Spec/development/test acceptances and their evidence must already exist at the merge commit. Closed Issues or editable metadata alone never establish completion.

Install the existing `.github/workflows/postmerge.yml` evidence workflow in each project. It must produce GitHubSource-compatible artifacts for required platforms. The consumer fetches the configured origin's main, checks exact commit ancestry, reads the card and hashed evidence in an isolated clone of that commit, and runs the existing pinned ReviewRunner. It rejects absent/failed CI and missing independent acceptance. Reviewer subprocesses omit GH_TOKEN/GITHUB_TOKEN; a worktree or clone is not a credential/process sandbox.

## Trusted runner installation

Register a self-hosted Actions runner using GitHub's repository Settings > Actions > Runners instructions. Assign a fixed project-specific label and restrict runner access to that repository's trusted workflows. Install Python 3.11+, Git, Task Tower and the reviewer separately. This repository does not register a physical runner or prove another machine is available.

Choose the Windows PowerShell `docs/templates/task-tower-project.yml` or Linux/macOS Bash `docs/templates/task-tower-project-posix.yml` template. Copy the selected file to the owning repository's `.github/workflows/task-tower-project.yml`, replacing its fixed label, project ID, trusted installed product directory, Python and private configuration paths. Review and commit that workflow on main before dispatching. The workflow uses server-side repository+Issue concurrency, `queue: max`, and does not cancel running jobs. Labels and assignees are not locks. Never add untrusted PR checkout/commands to this credential-bearing workflow.

An installation-private worker configuration (absolute state directory retained on the runner):

```json
{
  "state_dir": "C:/TaskTower/private/state/my-project",
  "issue_tasks": {"12": "docs/tasks/TT-EXAMPLE.json"},
  "required_platforms": ["windows", "macos", "linux"],
  "workflow": "task-tower-project.yml",
  "reviewer": {
    "kind": "codex",
    "timeout_seconds": 900,
    "superpowers": {"path": "C:/TaskTower/skills/SKILL.md", "sha256": "REPLACE_WITH_ACTUAL_64_HEX_SHA256"}
  }
}
```

The connection file uses the connections schema documented by `project_connections.py`: version 1 and projects containing id, repository, checkout and runner_label, with optional project_url. Configurations are local trust inputs. Protect them and state files with installation permissions. Issue text never selects executable arguments.

## Commands and durability

Run from the installed Task Tower checkout; options precede the action:

```powershell
python -m task_tower.project_worker --connections C:/TaskTower/private/connections.json --project my-project --config C:/TaskTower/private/worker.json dispatch --issue 12
python -m task_tower.project_worker --connections C:/TaskTower/private/connections.json --project my-project --config C:/TaskTower/private/worker.json reconcile
```

Dispatch appends an immutable queue intent comment to the Issue before requesting Actions; it never resets a running lifecycle. Reconciliation scans bounded comment pages and redispatches requested Issues after dispatch/API/queue failures. It also resumes publication for completed Actions attempts marked running/reviewed, or done while the Issue remains open. Active Actions runs and needs_input tasks are skipped. Resume without a valid matching receipt fails closed and requires explicit recovery; it never silently repeats the model. Actions queues are bounded (maximum 100 pending in max mode); overflowing jobs may be canceled. The Issue request plus periodic/operator reconciliation supplies durability, not an unlimited Actions queue. Duplicate dispatches serialize at the server; the consumer rechecks state.

The trusted project configuration selects a nonempty subset of Windows/macOS/Linux checks; duplicates and unknown platforms are rejected. The default for Task Tower is all three. The attested receipt records the owning project policy.

Successful review is atomically persisted in the private state directory **before** remote publication. A publication retry on the same durable state revalidates exact main, CI and card snapshot and reuses the receipt, without invoking the reviewer again. Keep that directory across runner updates. The workflow always uploads the minimal review receipt as an Actions artifact even after publication failure. Another runner may reuse it only after verifying the completed trusted workflow on main, artifact identity/digest, exact Issue/review identity and fresh CI/main evidence. Books use this attestation to show done. Before upload completes, after expiry, or if the artifact is missing, reads fail closed as needs_input. An interrupted model without a verified receipt requires explicit recovery. Editable Issue review metadata alone is never enough. Artifact retention is finite; preserve evidence or explicitly recover after expiry.

To recover, inspect the recorded Actions run and ensure all associated processes have stopped, then invoke `recover --issue 12 --confirm-stopped`. The command dispatches a recovery request to the same serialized workflow. Inside that job, recovery checks the old authoritative run is completed, resets the request to queued and removes its local receipt, then consumes it. Recovery explicitly authorizes a fresh review, including after state loss or changed evidence. Never confirm while another process still runs. Preserve the original state directory when only publication failed.

The `consume` action requires GITHUB_RUN_ID and is intended only inside the installed trusted workflow. Remote lifecycle is stored in append-only Issue comments. Closing uses a state-only PATCH; the worker never rewrites Issue prose. Comment pages are bounded and unavailable/truncated lifecycle data fails closed.

Local file-backed postmerge worker remains a separate legacy mode. No workflow is activated by adding the template to Task Tower.
