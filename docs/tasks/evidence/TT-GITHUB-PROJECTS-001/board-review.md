# Independent focused board review

Date: 2026-11-01. Scope: task_tower/projects_board.py, tests/test_projects_board.py and actual ProjectConnection validation. Verdict: changes required for the accepted configuration mismatch below.

## Finding

**P2: An accepted Project configuration crashes synchronization instead of reporting a mapping error.** ProjectConnection accepts a board with project_id alone: missing status_field_id and empty status_options are explicitly valid together. sync_issue unconditionally indexes board['status_field_id'] before its exception boundary, and main catches only ValueError/GitHubSourceError. Therefore a valid installation configuration causes an uncaught KeyError rather than an explicit not-configured/mapping-unavailable result. Require complete mapping at config validation, or handle incomplete mapping before mutation. Add a regression using the real ProjectConnection accepted shape, not only a SimpleNamespace with all fields.

## Verified design observations

- ADD and STATUS match the current official GraphQL input/return shapes. Separate add then single-select update follows GitHub guidance. Variables avoid query interpolation, the fixed HTTPS endpoint and no-redirect transport avoid credential forwarding, errors omit transport exception secrets, and Issue body done is not treated as trusted acceptance.
- [GitHub Projects API guidance](https://docs.github.com/en/enterprise-cloud%40latest/issues/planning-and-tracking-with-projects/automating-your-project/using-the-api-to-manage-projects) and [GraphQL Projects schema](https://docs.github.com/en/graphql/reference/projects), checked 2026-11-01. No live Project mutation performed.
- The six supplied tests exercise mutation order, unmapped status, redacted errors, unconfigured board, bad identity and untrusted done. All inject a graphql callback: the real transport envelope/error path and a repeat invocation returning an existing item are not directly tested. This is a meaningful coverage gap, not an observed API-shape failure.
- Per-project operation is explicit through one supplied connection and its repository-scoped store. No aggregate loop exists here; cross-project failure isolation belongs to the caller. The direct module CLI is a usable one-Issue operation, not automatic lifecycle synchronization.
- The direct CLI never passes verified_status. Consequently even genuinely accepted done remains needs_input when projected. Preserve this fail-closed behavior until trusted remote evidence is wired, but describe the limitation explicitly; do not claim complete accepted-done lifecycle projection from this command.

Review used static control-flow/config inspection and current primary API documentation. The default python command resolves to an unavailable WindowsApps alias in this reviewer environment, so focused test results were not independently reproduced here. Parent-reported red/green results are not represented as independent execution evidence.
