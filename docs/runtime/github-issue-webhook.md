# GitHub issue bot

The bot receives signed GitHub App webhooks on Vercel and consumes them in the existing foreground Task Tower connector. PostgreSQL stores transport/dedup/lease receipts. Beads owns tasks, dependencies, owners and acceptance history. Receiver health, a transport ACK and a finished model turn do not mean accepted delivery.

## Reporter flow

Use the [Task Tower issue template](../../.github/ISSUE_TEMPLATE/task-tower.md), or open an issue with these sections (English headings are stable; Russian aliases are also supported):

```markdown
## Reproduction
Steps to reproduce the problem.
## Expected behavior
What should happen.
## Acceptance criteria
How to check the result.
## Files
- docs/existing-example.md
```

Missing sections produce a clarification comment. Add the sections in an original-reporter comment or edit the issue. Only the original numeric reporter can supply clarification context. Admission requires the repository owner or freshly verified push rights. Other reporters wait for owner admission; issue prose cannot grant permissions.

The initial automatic scope covers declared existing regular Markdown/Python files only, with sensitive execution/auth/admission modules excluded. New files, unknown classification, unavailable narrow sandbox, exhausted budgets and revoked rights stop automatic execution. The current conservative implementation requires existing files; the general policy allowlist does not imply every possible change is automatically executable.

The connector claims and executes native work through the existing lifecycle. Independent review precedes a candidate PR. The bot publishes its exact commit and checking instructions. Test that version on your device, then reply as the original reporter:

```text
/task-tower verified <full-40-character-lowercase-head-sha>
```

To report a problem with the same candidate:

```text
/task-tower changes <full-40-character-lowercase-head-sha>
```

Changed head/base, edited/deleted verification and a later explicit changes request block merge. Waiting for a reporter does not reserve the repository merge lease. Merge still requires independent exact-H/B review, actual CI, genuine acceptance status and unchanged protection. The original issue closes only after exact-main/postmerge acceptance and canonical close/history readback. Public-effect uncertainty preserves its intent and requires factual readback; it does not replay development or native closure.

Delayed public closure also requires the admitted request revision to remain unchanged and no reopen event since admission. A changed or reopened request stays open for its owner; an older accepted result cannot close it. Comments on pull requests are acknowledged as ignored and do not enter issue admission.

## Operator setup

Deploy only accepted source after final review, mandatory tests/CI and protected main acceptance. Existing unknown attempts, claims, repository leases, paused automation and user WIP remain untouched. This runbook grants no recovery, capacity change, service restart or account change.

1. Use the isolated new Vercel project approved for this integration. Build a fresh staging directory from clean committed source:

   ```console
   python -m integrations.github_webhook.package --out <new-private-staging-directory>
   ```

   Only the fixed receiver, schema, Python dependency/config files and five route wrappers are copied. The App key, host modules, private configuration, repository metadata and host signing dependencies are excluded. Configure deployment Root Directory for the staging root, not an unrelated checkout. Python 3.12 is pinned in the staged pyproject. The package receipt identifies source/files; it is not acceptance evidence.

2. Provision the explicitly scoped free PostgreSQL database and apply `integrations/github_webhook/schema.sql` to that new database only. Use an isolated host environment for `integrations/github_webhook/host-requirements.txt`; the Vercel staging requirements are separate. No global package installation is needed. Verify PostgreSQL durability/rollback/races on a dedicated test database; the optional command below is only an initial transaction smoke, not the entire deployment gate:

   ```console
   python -m integrations.github_webhook.inbox --check-postgres
   ```

   It reads `WEBHOOK_TEST_DATABASE_URL` from trusted environment and requires the receiver schema. Never put DB URLs, App keys or consumer secrets in argv, prompts or public output.

3. Create the GitHub App with real owner consent. Prepare the public manifest for the actual accepted receiver origin:

   ```console
   python -m task_tower.issue_operator manifest --receiver-url https://<accepted-receiver-origin> --out <new-manifest-file>
   ```

   Use that manifest in GitHub's App registration flow and install only the authorized repository. Keep the downloaded/generated private key on the host with private file permissions; never upload it to Vercel. Permissions are metadata read; issues/contents/pull_requests/statuses write; actions/checks/administration read. Administration is read-only for protection checks. No workflows/admin write. Subscribe to issues and issue_comment. Never automate a fabricated installation consent.

4. Through trusted local secret transfer, configure Vercel `WEBHOOK_BINDING` (numeric app_id/installation_id/repository_id), `WEBHOOK_CONSUMERS` (consumer identity, binding and credential_sha256), `WEBHOOK_SECRET`, and `WEBHOOK_DATABASE_URL`. Supply only the scoped consumer credential to the host. A signed `ping` completes the handshake without task/native effects. Other webhook 2xx responses require durable transport receipts. Health is read-only; consumer endpoints require the scoped bearer credential.

5. Add matching startup-only `issue_connections` to the two existing host operator configs. The issue App binding is host-only and is rejected for the separate container-network service route; do not put executor repositories or App/GitHub credentials in Docker. Each project entry has exactly: `app_id`, `installation_id`, `repository_id`, `repository`, `connector_id`, `app_server`, `source_repository`, `private_key_file`, `policy_file`, `policy_sha256`, `consumer_id`, `consumer_token_file`, `transport_url`. File/executable/repository locators are trusted absolute paths and never enter model/API packets. `source_repository` is the registered Git checkout. `app_server` must match the connector executable. The repository is fixed by the approved policy. Do not add a second connector or increase occupied capacity. No model or approval-policy selection is accepted by this binding.

6. Keep the committed policy example disabled. Its exact approved activation changes only `initially_enabled`; pin the actual policy file bytes with `policy_sha256`. Check the prepared binding and run the model-free runtime probe explicitly:

   ```console
   python -m task_tower.issue_operator check --config <private-connector-config>
   python -m task_tower.issue_operator probe-runtime --config <private-connector-config> --receipt <new-private-receipt-file>
   ```

   The probe uses disposable synthetic files and fixed sandbox commands, with no model turn, global permissions change, native claim or Task Tower service startup. Its network negative control targets only `api.github.com:443`, after the trusted host confirms that endpoint is reachable; a closed localhost port or timeout never counts as proof of denied network. Individual results/error codes are retained even on failure. A failed/unknown probe is fenced rather than automatically retried. If the installed runtime cannot prove declared-file write, denied unrelated/private writes/reads and denied network, intake stays disabled/needs_input. No silent workspace-wide fallback is allowed. Existing structured approval callbacks still require the actual operator; policy admission never auto-approves them. Git commit approvals may remain necessary under the existing account requirements.

7. Cut over only the explicitly authorized existing owned bindings after source acceptance and verified cleanup/identity receipts. Retain journals and all existing fences. Startup-only binding/policy changes cannot be smuggled through append-only assignment reload. Then verify actual SQL transactions, valid/invalid HMAC HTTP, duplicate delivery, host offline/reconnect, App installation/status/push identity and a real cross-device reporter cycle. Record real public result links without secrets. Do not call a fixture or this runbook a completed pilot.

## Development and acceptance

During development, run the addressed new-bot test only. Run the complete tower suite at final acceptance:

```console
python -m unittest discover -s tests -v
```

Final Reslop follows the owner rule: once at the end of the complete cycle, after authorized independent review/corrections and before final merge; preserve raw output and all mandatory original assertions/skips/timeouts. No per-stage PRs or repeated whole-tower runs are required by this feature.

Verified documentation references on 2026-11-11: [GitHub App JWT](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/generating-a-json-web-token-jwt-for-a-github-app), [Vercel Python API directory](https://vercel.com/docs/functions/runtimes/python/api-directory), [Codex App Server](https://learn.chatgpt.com/docs/app-server), [permission profiles](https://learn.chatgpt.com/docs/permissions). Real deployment/installation/reporter acceptance must be recorded separately.
