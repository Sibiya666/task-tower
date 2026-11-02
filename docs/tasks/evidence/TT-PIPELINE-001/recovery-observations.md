# Issue16 recovery observations

This record preserves unsuccessful runs, scoped experiments and the limits of their conclusions. It grants no acceptance by itself. The independent development/TEST reports and exact-head CI/PR gate determine whether a recovery candidate can merge. Exact-main CI, an independent postmerge reviewer and publisher-driven Issue/Project closure remain separate requirements.

## Main and initial recovery

PR #41 merged as `d5cf8953b70caf5329d5173b7fb4a15eaa4df978` after six green exact-head checks and independent PR acceptance. Postmerge run [41451105738](https://github.com/Sibiya666/task-tower/actions/runs/41451105738) succeeded on Linux and macOS; Windows job `125296237186` exceeded the workflow's 15-minute limit. Its cancelled test step and exported failed outcome are not passing proof. Issue16 stayed open and the local worker projected `postmerge_failed`.

The bounded recovery raises that workflow job limit to 45 minutes. The preceding final-head Windows push job had taken about 30 minutes. The complete suite, exact merge checkout, three-platform matrix, failure export and final failure gate remain required. See [initial timeout record](postmerge-timeout-recovery.md).

Initial recovery PR #42 head `3de7f94c7b7f40293a8cf673bc68877fba377830` then exposed additional failures:

| Observed run/job | Actual result |
| --- | --- |
| Push `41454455412`, macOS `125307466163` | One early `unknown` assertion in publication preparation; 716 tests, 410.948 seconds, seven skips |
| PR `41454526264`, Windows `125307708054` | Three read-only SQLite errors in watch tests; 716 tests, 1947.947 seconds, one skip |
| Other four checks at that head | Success |

The failing fixtures were not retained by those CI runs. The exact underlying causes of the original macOS and Windows failures remain **unproven**. Matching an error message or passing another run does not establish causation.

## Cancellation-observation latency

Five bounded local executions of the actual lost-PR-response test passed. One nevertheless captured an actual cancellation callback exception: its 0.2-second journal-operation deadline expired before connecting to SQLite. A separate isolated causal probe waited for a genuine owned role and durable launch intent, performed real path validation and delayed that validation by 350 milliseconds. The managed host became unknown; recovery retained the unresolved attempt as unknown/owner_dead. No process result or authorization predicate was fabricated.

The correction allows one bounded second for this observation and checks stop immediately before and after the read. Read errors and over-budget observations still propagate to unknown fencing. Role/task/check budgets and the shared shutdown limit are unchanged. Actual owned-role regressions cover the healthy 350-millisecond case, an over-one-second unknown/no-replay case and cancellation during the read with positive contained cleanup.

The separate diagnostic macOS branch ran 20 actual cases successfully at `c4585570b480ed46bf2f123100bf533b6ff0ddeb`, [run41457800297](https://github.com/Sibiya666/task-tower/actions/runs/41457800297). Instrumentation can affect timing. This was diagnostic evidence, not PR qualification, and did not establish the original macOS cause.

## Hot rollback journals and bounded shutdown

An isolated valid journal with 80 actual submitted rows was interrupted during a real SQLite cache-spill transaction. The child exited23 and left a hot rollback journal. Both a read-only SELECT and the actual journal's read-only startup encountered `SQLITE_READONLY_ROLLBACK` (776). Read-only probes left the crash bytes intact; explicit existing recovery restored the prior committed state. This reproduces a possible mechanism for the Windows error pattern, not its uncaptured original cause.

The shutdown correction recognizes only an actual chained SQLite error with extended code776. Before recovery it requires positive cleanup from every contained host and uses the original shared deadline. Its private existing-database context covers recovery, subsequent reads/writes and final confirmation. Connections cannot create a missing database or initialize an empty/foreign one. Exact schema, DELETE/FULL durability, regular single-link/non-reparse paths and physical file identity remain checked, including before commit and success. Public status remains read-only; ordinary startup behavior is unchanged.

Independent review rejected the first implementation: deleting the database after recovery made the default status read appear empty and falsely confirmed shutdown. The revised context makes this failure remain uncertain. Tests cover disappearance/replacement after recovery and before cancellation/controller operations. An explicit cancellation still records its request for the exact worker-owned UUID after recovery marks the run unknown. Normal completion invents no cancellation; unrelated owners and unknown fences remain intact.

One pre-commit test initially expected the deleted pathname to remain absent. Actual SQLite rollback restored the original valid database on Windows. The corrected expectation requires failed confirmation, the complete prior rows/schema/owner/cancel state and no recovery/cancel events or replay. No valid restored database is deleted to satisfy a test. This is rollback behavior, not schema initialization.

## Delivery-journal metadata races

A subsequent combined run at the revised source passed95 of96 tests but failed a delivery-journal read. The wrapper suppressed the underlying exception, and the disposable fixture had been cleaned. That particular failure remains unattributed.

A separate 30-second genuine delivery-journal churn test completed1796 writes and1211 reads without error. A separate actual six-role watch test also passed. Neither observation explains the failed combined run.

Two deterministic timing probes then used a real SQLite writer: an actual existence check observed its own sidecar, the writer committed and unlinked that file, and the original read continued with its previously observed result. Both the later stat and alias-check boundaries raised actual `FileNotFoundError`. These are independently demonstrated races in the guard, not proof about the lost fixture.

The correction reuses the existing strict private-stat helper. Only the journal's three explicitly derived SQLite sidecars receive transient treatment. The primary database and positively observed forbidden inputs stay strict, including inputs named with a journal suffix. Validated stat snapshots support alias comparison without a second racy lookup; canonical/checkout, regular-file, hardlink, reparse, WAL and read-only guards remain. Real underlying errors are chained privately while the public error text remains neutral. No backend, delivery identity, schema, recovery or replay policy changes.

## Evidence and completion boundary

Private raw artifacts remain outside the repository. Selected SHA-256 bindings:

| Evidence | SHA-256 |
| --- | --- |
| Owned-role cancellation causal manifest | `60b4bfdda92cb5032289dbd33098a5606cbf45f9b340c38197890d0c5f9d905f` |
| Diagnostic macOS complete decoded log | `cf90e5f5fa93e2c03679d943e21409b4ea4a4f88bb33cf3d9db92458dfe6c8b0` |
| Independent initial hot-fallback rejection | `74988a7db34ce49fb3c13e44610bd50c119eadfb5ceb67cd6a425f2a66207dfb` |
| Failed96-test complete log | `1801f38e646fe3527c8e44e205c75fefba99dc85404d6aa34c6c211fd658dd79` |
| Delivery-journal deterministic barrier proof | `30844230309ba10d4716052fefdba4a2e52311995f426766088339da4ca98438` |

Earlier rejected, interrupted and unknown attempts, all1054 preserved installed-Codex pilot artifacts and their exact source-qualified limitations remain unchanged. The corrections do not constitute a new installed-model pilot or change the role wire contract. Current functional verification is recorded in the independent stage reports; fresh complete CI, exact-head/base PR acceptance and the new exact-main automatic closure cycle are still mandatory. No Issue is manually closed and no historical failed run is rewritten.
