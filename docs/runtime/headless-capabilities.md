# Headless capability observations — stage 1

Observed 2026-11-07 for `tt-20n.1`, from accepted main
`b8f8598e869eef79f404a41f085bbfe3f777f5eb`.
Both required capability paths are now confirmed. Independent review and the
repository delivery gates remain pending; canonical `tt-20n.1` is not accepted or
closed. Stage 2 has not started. No product connector/service has been implemented.

## Authority and reproducibility

See the approved [design](../superpowers/specs/2026-11-07-headless-release-design.md)
and [plan](../superpowers/plans/2026-11-07-headless-release-plan.md), including their
original digests and repository provenance. The earlier preparation baseline is
historical. `tt-qrk.6` was read back as closed without changing it. UI is excluded.
An isolated branch preserves the original checkout's WIP and previous CI receipts.

The installed binary reports `codex-cli 0.166.0-alpha.6`. After checking
`codex app-server --help` and `codex app-server generate-json-schema --help`, public
schemas were generated with `codex app-server generate-json-schema --out <private-output>`.
The [fixture](../../tests/fixtures/app_server_protocol.json) contains only the
generated public request/notification subset and its transitive definitions.
It contains no account settings, executable/database locators or runtime IDs.
Responses and unselected methods require the full schema regenerated from the
same installed binary; this subset is not a complete implementation specification.

## Confirmed stdio transport

Launch an owned subprocess with `codex app-server --listen stdio://`; exchange
newline-delimited JSON on stdin/stdout, with separate private stderr capture.
Do not use `daemon`, `proxy`, or connect to the desktop's app-server. This probe
used the existing account/model/policy without configuration overrides. It removed
`GH_TOKEN` and `GITHUB_TOKEN` case-insensitively from the child environment.
No token was read or supplied in arguments. Background Windows process launch
used `CREATE_NO_WINDOW`; `Start-Process` launchers must use `-WindowStyle Hidden`.

Observed inherited settings were `gpt-6.1-sol`, provider `openai`, approval policy
`on-request`, approval reviewer `user`, and `workspaceWrite` with network access
false. These observations do not authorize changing another session's policy or
expanding permissions. The smoke only returned a fixed string; no tool action or
filesystem editing capability was demonstrated.

| Method/event | Request or result actually observed |
| --- | --- |
| `initialize` | `clientInfo` with name/title/version; successful response, then `initialized` notification |
| `thread/start` | Only trusted own test `cwd`; distinct executor and reviewer thread IDs |
| `thread/read` | `threadId`, `includeTurns:false`: metadata worked before and after the turn |
| `turn/start` | `threadId`, `input:[{type:"text",text:...}]`; response `result.turn.id`, status `inProgress` |
| `item/completed` | Agent message text `CAPABILITY_OK` |
| `turn/completed` | Matching turn ID with status `completed` |
| `thread/read` with history | `includeTurns:true` succeeded for the populated completed thread |
| `thread/turns/list` | Own populated `threadId`, `limit:10`: successful response |
| `thread/resume` | Own completed `threadId`, `excludeTurns:true`: successful response; no new turn sent |

Empty-thread `thread/read(includeTurns:true)` returned JSON-RPC error `-32601`,
`list_turns is not supported yet`. This is a real empty-history limitation:
metadata reads worked and populated history subsequently worked. Do not replace
the error with invented history or read raw Codex databases. A separate reviewer
thread was created; this does not constitute substantive independent review of
this branch, and no reviewer verdict is inferred from the harmless smoke.

The [official app-server documentation](https://learn.chatgpt.com/docs/app-server)
provides the protocol background. Installed-schema and real-runtime observations
above determine this record's claims; documentation alone is not runtime proof.

## Disconnect and crash boundaries

A disposable HTTP fixture bound to `127.0.0.1` first returned a health response.
After `turn/start` acknowledged `inProgress`, only that listener was shut down.
The next HTTP request failed, the owned app-server process remained alive, and
the same turn completed with `CAPABILITY_OK`. A timestamped follow-up smoke received completion 6.109 seconds after the HTTP
request failed, with the same acknowledged turn and a live app-server. This proves
separation for this probe; it does not test a production orchestrator, durable outbox, or event replay.

A separate owned app-server was terminated immediately after an acknowledged
`inProgress` harmless arithmetic-check turn in its separate reviewer thread.
No matching completion was observed. The probe retained `unknown/interrupted`,
with one `turn/start` and no replacement/retry. This is a bounded crash observation
and conservative probe classification, not an implemented recovery mechanism.
No unrelated process was terminated. Completed history/resume never proves that
a crashed process or interrupted turn continues. RPC IDs only correlate responses;
`turn/start` idempotency remains unproved and ambiguous starts must not be retried.

## Docker and Linux Beads — confirmed

Initial bounded discovery found no Docker executable in PATH or the checked
standard locations; that observation did not establish global absence. The user
then directly authorized Docker installation, the two admin Windows prerequisites
without automatic reboot, and later the disposable Linux dependencies below.

Official Docker Desktop 4.98.0 (build 245422, 2026-11-03 release) x64 installer had
a Valid Authenticode signature from Docker Inc. Its SHA256 matched the
[official versioned checksum](https://desktop.docker.com/win/main/amd64/245422/checksums.txt):
`cd6273d9eaa4f07fa7593fc6813d37e1004381cebc3f26047a2554fa5db24388`.
The pinned download is linked from the
[official release notes](https://docs.docker.com/desktop/release-notes/#4980).
Per-user installation used `install --user --quiet --backend=wsl-2
--no-windows-containers --accept-license`. The first attempt exited 1 because
VirtualMachinePlatform was disabled. Following explicit approval, only WSL and
VirtualMachinePlatform were enabled using `-NoRestart`; both read back Enabled
with RestartNeeded true. The second installer attempt exited 0. Its ordinary
current-user shortcuts, PATH and product registration were installed. No all-users
service, docker-users membership or firewall change was requested.

The user rebooted Windows. Post-reboot diagnostics showed old inbox WSL without
its WSL2 kernel. The official Microsoft WSL 3.0.3.0 x64 MSI was then installed as
the missing Docker prerequisite, with `/norestart REBOOT=ReallySuppress`; exit 0.
Its Microsoft Corporation signature was Valid, and SHA256 matched the
[official release asset](https://github.com/microsoft/WSL/releases/tag/3.0.3):
`ae977286974255bd26bf925f00f40f5692c6b2084155cbc0563c09aea091f211`.
No distribution was installed by this MSI. No automatic reboot or Windows Update
policy change was performed. `wsl --version` now reports WSL 3.0.3.0, kernel
6.18.54.1-1; `wsl --status` exits 0 with default version 2. HypervisorPresent is true.
Docker Desktop was restarted through its supported CLI, with a 120-second command
timeout. A `docker info` call during startup timed out after 20 seconds; that
failure is retained. After Desktop reported running, a fresh read succeeded.

Actual engine readback: Docker Server 29.9.2, OSType `linux`, architecture `x86_64`.
CLI is 29.9.2 (`a82e528`), Compose is v5.6.1. Initial running-container count was
zero. The host is Windows 10 Pro 19045.6456 x64, about 31.8 GiB RAM, with firmware
virtualization and SLAT true. Runtime success does not prove Microsoft's
servicing/ESU eligibility, which was not verified. See
[Docker's Windows requirements](https://docs.docker.com/desktop/setup/install/windows-install/).

### Verified disposable Linux path

The user explicitly approved downloading the official Debian image, Git inside
the container and Beads 1.3.4 with embedded Dolt. No canonical host database or
working repository was mounted, copied or migrated. Build context contained only
the pinned `bd` binary and the private probe Dockerfile; no model or GitHub auth
was supplied. This capability image is not the release's Task 6 Dockerfile.

| Component | Actual pinned identity |
| --- | --- |
| Debian trixie-slim Linux amd64 manifest | `sha256:7378260c0a098d27ac206225db5e7d92b8c7c84ea7afccc86eeb513756bbd392` |
| Beads 1.3.4 upstream release commit | `7ef2fd05eb0cd3bdbde051f93cfc14ccf270cdde` |
| Linux amd64 release archive SHA256 | `175c26904bde3ff9168d2282ff6b56f17b17f60c22fa5acb3dacc9fb3465303a` |
| Extracted Linux `bd` binary SHA256 | `9185e9798ba044b288e781f7d57f28a48f558654e94572473e49991826e69930` |
| Tested local image ID | `sha256:e6499d3f25c46c445673692fb9a2374fd95e01379bd9a73c213ba6b51bb84f82` |
| Git / libc6 / CA package versions | `1:2.47.3-0+deb13u1` / `2.41-12+deb13u4` / `20250419+deb13u1` |

The [upstream 1.3.4 release](https://github.com/gastownhall/beads/releases/tag/v1.3.4)
matches the existing host `bd` version/commit. Embedded mode needs no standalone
Dolt binary or server. The [pinned source go.mod](https://github.com/gastownhall/beads/blob/v1.3.4/go.mod)
declares `github.com/dolthub/driver/v2 v2.2.0` and
`github.com/dolthub/dolt/go v0.40.5-0.20260806213044-796d07497741`.
These identify embedded build dependencies, not a separately executed `dolt version`.
Real embedded database operations below, rather than that declaration alone,
establish the tested path. The build used signed Debian package repositories;
the package versions and resulting image ID were recorded. A later reproducible
release build still needs to pin package sourcing, rather than assume mutable apt
repositories reproduce this image forever.

After build, the test container had network `none`, no published ports, all Linux
capabilities dropped, no-new-privileges, and one dedicated named volume at `/data`.
No bind mounts or GitHub-token environment variables were present. Only an
explicitly created disposable card was used:

1. `bd init --prefix pilot --non-interactive --skip-agents --skip-hooks` created a
   new embedded database; `ready --json` initially returned an empty list.
2. Create returned the real test card ID; `ready` contained it. Atomic
   `update <id> --claim` and fresh `show` agreed on status `in_progress` and the
   dedicated test actor as assignee.
3. `history <id> --events --limit 0 --json` returned actual `created` and `claimed`
   events with their true actor/times. Commit history contained two snapshots.
   A probe assertion initially expected another event name; it was corrected from
   the recorded native output without replaying init/create/claim.
4. `backup init /data/native-backup`, `backup sync` and `backup status` succeeded.
   A separately initialized restore target was confirmed empty. Native
   `backup restore /data/native-backup --force` was scoped only to that disposable
   empty target, never the host canonical database.
5. Restored identity, description, status, assignee, owner and original chronology
   matched; both complete audit events and both commit snapshots compared equal.
   The claimed card stayed absent from restored `ready`.
6. The owned container was stopped and read back as not running. Its disposable
   volume, stopped container and test image are retained as evidence, not a worker.

This confirms the stage 1 Linux ready/claim/readback/history/native-backup/restore
path. It does not migrate the production backlog or implement the service API.

## Receipt and acceptance boundary

Private receipts preserve the native claim/readback, initial sandbox failures,
generated full public schemas, owned-process RPC captures, summaries, and installer
failure. They stay outside Git. The shared plan ledger records these observations
and rulings for later sessions. No runtime acceptance, full release readiness,
canonical close, PR acceptance or exact-main delivery is claimed by this document.
