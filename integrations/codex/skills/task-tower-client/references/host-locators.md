# Resolve the actual host binding

Use the current operator-supplied Task Tower source checkout, registered project ID and trusted private connector-config locator. These are separate facts. A source checkout is not a service endpoint or project registration; a chat title is not a binding.

Before using the client, verify that the actual source contains `task_tower/connector/cli.py`, `docs/project-intake.md` and `docs/runtime/headless-operation.md`, and read the supported interfaces there. Do not assume the current working directory is Task Tower. Use the host's already installed explicit Python interpreter with that verified source as the working directory.

If an older checkout lacks the client, report the mismatch and use a current authorized source locator. Do not substitute a private native-Beads helper for Task Tower scheduling, or reset/stash/pull/overwrite someone else's WIP to obtain the client. On another host, resolve that host's actual paths instead of copying the previous machine's paths.

Use only the supplied registration/config locator. Do not scan private runtime files or databases, guess an endpoint, request token contents, or interpret this instruction package as deployment/startup permission. Missing source, registration, connection or observation access remains a specific unresolved connection gap.

Repository source: [Sibiya666/task-tower](https://github.com/Sibiya666/task-tower). The chosen checkout's `docs/project-intake.md` and `docs/runtime/headless-operation.md` govern its actual operator contract. Reading repository source is not deployment or authorization to install/start a service.
