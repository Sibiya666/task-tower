# GitHub setup from a clean clone

Task Tower requires Python 3.11+ and an installed harness. It does not install software, choose a model, grant permissions or start a background development service. Local-only `python bootstrap.py` remains available; a successful local harness configuration does **not** establish GitHub readiness.

## Install and authorize GitHub CLI

On Windows, install GitHub CLI through its official winget package:

```powershell
winget install --id GitHub.cli --exact
```

Open a **new terminal** so PATH changes apply, then check `gh --version`. On macOS/Linux follow the [official GitHub CLI installation instructions](https://cli.github.com/manual/installation). Authentication is an explicit human step:

```sh
gh auth login --hostname github.com --web --scopes repo,project
gh auth status --hostname github.com
# For an existing CLI login lacking Projects authorization:
gh auth refresh --hostname github.com --scopes project
```

Read and approve the requested permissions yourself in GitHub. Organization policies may require additional administrator approval. Task Tower never runs login/refresh or silently expands scopes. Use the normal secure credential storage offered by GitHub CLI. Do not place tokens in descriptors, connection JSON, shell history or repository files. A GitHub app connector login and Git Credential Manager's Git transport login are separate from local `gh` authorization; a working clone/push or connector does not prove Projects access. Existing environment credentials can override CLI credentials, so ensure the credential actually used has the required repository and Projects write access.

## Connect the repository before importing Issues

Clone Task Tower and the repository you want to manage. Run these commands from the Task Tower clone; replace `OWNER/REPOSITORY`, checkout path and runner label with your own values. The private config belongs to this installation **outside both source checkouts**. The runner label records a routing identity; it does not install a runner.

```powershell
$connections = Join-Path $HOME '.task-tower/connections.json'
$checkout = (Resolve-Path 'C:/work/my-project').Path
python -m task_tower connect --config "$connections" --id my-project --repository OWNER/REPOSITORY --checkout "$checkout" --runner-label my-project-runner
```

macOS/Linux equivalent:

```sh
python3 -m task_tower connect --config "$HOME/.task-tower/connections.json" --id my-project --repository OWNER/REPOSITORY --checkout /absolute/path/my-project --runner-label my-project-runner
```

`connect` verifies the authenticated repository identity, reuses a suitable linked Project or creates/links one when none exists, and establishes the managed Status options before saving the private connection. To select an existing board explicitly, add `--project-url https://github.com/users/OWNER/projects/NUMBER` (or `https://github.com/orgs/OWNER/projects/NUMBER`). Multiple candidates require explicit selection. The board must belong to the repository owner and support the required access and status mapping. A URL alone in a legacy connection is not complete onboarding.

Only after successful connection import a task card:

```powershell
python -m task_tower books --connections "$connections" --project my-project --import-card C:/work/my-project/docs/tasks/TASK-001.json
python -m task_tower books --connections "$connections" --project my-project
```

Project failure blocks new Issue creation. Existing Issues keep their identity and prose; repeated imports repair membership/status rather than deliberately recreating them. An error after Issue creation reports a partial result: retain its URL/number, restore access and retry the **same card**. Do not manually delete the Issue or board. After remote success and local config failure, retain the reported Project URL and rerun with `--project-url`; resolve the local conflict first. Serialize initial connections/imports across machines: bounded reconciliation is not a distributed exactly-once creation lock.

Task Tower commits a private creation intent before each Project or Issue create request. Keep `<connections-file>.create-intents.sqlite3` beside the installation config and `<checkout>/.task-tower/create-intents.sqlite3` through retries and private backups; these journals contain identities and resolved resource IDs, never credentials or Issue prose. A timeout can mean GitHub is still processing the request. A later invocation reconciles a uniquely matching remote resource but refuses another create while the prior outcome remains unresolved, even when discovery currently returns nothing. Inspect the repository/owner Projects, restore access, and retry the same configuration/card after the original resource becomes visible. For a Project, pass its actual `--project-url`. Do not delete, replace or silently reset a journal to bypass uncertainty. A moved checkout/config must retain its journal. These local guards do not provide cross-host creation serialization.

## Connect through the installer

The same explicit connection can precede harness configuration or launch:

```powershell
python bootstrap.py --project "$checkout" --harness codex --superpowers C:/skills/using-superpowers/SKILL.md --github-repository OWNER/REPOSITORY --connection-id my-project --connections "$connections" --runner-label my-project-runner --configure-only
```

Add `--project-url URL` to select a board, or use `--launch` to start the selected harness after successful setup. All four identity/config flags are required together. A Projects denial stops before harness configuration or launch. `--dry-run` only prints an **unverified connection plan**: it neither calls GitHub nor writes private connections and cannot prove board readiness. GitHub flags are explicit per invocation; saved local harness choices do not imply a new GitHub check on subsequent local-only launches.

See [bootstrap/custom harness setup](bootstrap.md), [connections and books](github-books.md), [runner configuration](github-projects.md) and [the development roadmap](roadmap.md). The supported launch adapter is interactive; autonomous callbacks, resume, executor orchestration and daemon operation remain planned.
