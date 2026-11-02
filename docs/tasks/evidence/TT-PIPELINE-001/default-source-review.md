# Independent review — production collector defaults

Date: 2026-11-02. **ACCEPT at the exact two-file bindings below. No blocking findings.** This verdict covers only the production-default integration correction and its new tests; it does not accept unrelated Task 5 edits, unfinished watch behavior, the whole Issue, PR or main.

Base HEAD: `761a1195f5575bc6689d7eb31cb2a9097a53c755`. Reviewer is distinct from the implementer. Read the entire actual `dispatch_selection.py` diff and new test module, the existing dispatcher factory and explicit call sites, GitHubTasks/GitHubSource authentication constructors, and genuine pipeline admission, worker/role authority callers. Prior complete design/plan review and ledger rulings remain applicable. Applied Superpowers independent review and verification guidance. No product edits, commits, pushes, credential changes or live API writes were made.

## Exact review inputs

Independently recomputed raw SHA-256 and `sha256-utf8-lf-v2` canonical SHA-256:

| File | Raw SHA-256 | Canonical SHA-256 |
| --- | --- | --- |
| `task_tower/dispatch_selection.py` | `b364166a0e399af3e56f3c7ce074d0b91430829a0d4cb9d134b390052ec837f8` | `062d52a32a4cc794eb648c80c9d51613b5f118f271abf87d26c6d2969a80badc` |
| `tests/test_pipeline_default_source.py` | `9bebfd4fe268655b6ee39608d0704619bf2516c7c734b07a81c4e69cfea53260` | `9bebfd4fe268655b6ee39608d0704619bf2516c7c734b07a81c4e69cfea53260` |

## Findings and reasoning

The earlier keyword-only required `store_factory`/`source_factory` contract was incompatible with production pipeline admission and authority calls that pass only connections. Existing collector mocks hid this prelaunch TypeError. The fix adds optional defaults at the shared collector seam while leaving its selection, lifecycle, identity, failure-isolation and dependency-verification bodies unchanged.

Omitted store factory resolves to the actual GitHubTasks class; omitted source factory resolves lazily to the existing `dispatcher._source`. That factory still constructs GitHubSource with its existing host token resolver. No new credential flow, scope, source type, receipt verifier or permissive fallback is introduced. Constructors and authentication occur per connection under the collector's existing exception/failure isolation. The lazy imports run after module initialization and do not add module-load authentication/network effects. Explicit non-None factories retain precedence independently, so callers may supply either one or both. The existing dispatcher still passes both explicit factories unchanged. `verified_done` and the genuine selection/dependency receipt checks are unchanged.

The new integration tests leave the collector, constructors, admission, continuation, registered owner journal, worker authority, role runner and actual child process intact. Substitutions are limited to existing authentication and GET HTTP transport seams. The real child produces its bound result and increments the genuine journal process count once. Tests reject HTTP failure before any launch intent/attempt and reject a closed dependency whose editable metadata merely says done. This does not claim verified positive dependency receipt coverage was newly added: existing dispatcher/selection suites continue to cover the established verifier contract.

## Fresh independent verification

Runtime: `C:/Users/sibiya666/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe`, Windows host.

Command: `-m unittest tests.test_pipeline_default_source tests.test_dispatch_selection tests.test_dispatcher -v`.

Actual result: **32 tests in 6.996 seconds, OK; 32 passed, zero failures/errors/skips.** Includes all six new default-source tests, existing selection/dependency tests and all existing dispatcher tests, including authenticated source forwarding, fresh final source failure, authorization revocation, no duplicate delivery and unknown lookup behavior. Both-factory explicit injection forbids unexpected default authentication; each one-factory injection preserves the other genuine default.

Additional independent cold-process probes used the same absolute Python runtime with no API calls: import collector first, call default collector with an empty connection set, then import dispatcher and call with its explicit source; and import dispatcher first, then collector and its default call. Both fresh interpreters exited zero. This checks lazy-import/circular-import compatibility in both directions rather than relying only on an already warmed test interpreter.

Reviewer command correction: the first invocation also named nonexistent `tests.test_dispatcher_integration`; its 32 real tests passed but unittest reported one module-load error. This was a reviewer command mistake, not a product failure. The corrected complete valid command above was freshly rerun and passed. Author-reported focused/full-suite results were not counted as this reviewer's evidence.

No collector mock, continuation-true predicate or verified_done-true predicate was used for this review's new production-default validation. No full-suite, three-OS CI, live GitHub receipt/publication, installed-Codex pilot or unfinished Task 6 watch acceptance is claimed. Separate frozen Task 5 files and unrelated runtime artifacts were preserved. Any change to either bound file invalidates this scoped verdict and requires a fresh review.
