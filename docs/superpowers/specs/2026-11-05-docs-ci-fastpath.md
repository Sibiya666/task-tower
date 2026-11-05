# Truthful documentation CI fast path

Canonical Beads task: `tt-qrk.2`. The owner wants documentation changes to avoid full runtime CI. The accepted parallel-suite route remains the default for code, mixed and uncertain changes. Existing flaky preparation bug `tt-qrk.4` remains open; this feature does not fix it.

## Scope and conservative classification

Add standard-library helper `task_tower/ci_docs.py`. For the actual checkout, inspect Git objects only, not private settings or paths outside the repository. A fast path is allowed only when HEAD has exactly two parents (the authorized normal merge route), both parent objects are available, and every full first-parent-to-HEAD change is regular non-executable prose: root `README.md`, root `AGENTS.md`, or nonhidden `.md` files under `docs/`, excluding `docs/templates/`.

Use raw NUL-delimited Git diff with renames disabled so old and new names are both classified. Reject executable/symlink/gitlink modes, hidden/traversal/control-character paths and malformed metadata. Empty changes, missing history, single-parent/squash/rebase ambiguity, code/workflow/template/mixed changes or unknown forms select **full runtime checks**, never docs success. Normal PR proposed-merge checkout and postmerge exact-merge checkout use depth2, enough for both direct parents. This bounded initial policy intentionally does not optimize squash/rebase/direct-push/merge-queue routes.

## Bounded documentation validation

The docs path runs `git diff --check` and rejects newly broken local Markdown links against the full tracked prose inventory. Compare head and base so pre-existing historical broken links do not block unrelated corrections, while deletion/rename of a target is detected even when its referring file was unchanged. Check supported inline links/images and reference destinations; skip fenced/inline code, anchors and external schemes without network access. Document that this is local-link checking, not a complete CommonMark renderer or external URL checker.

The referring-file inventory includes all regular tracked `.md` blobs, including Markdown outside the narrow fast-change allowlist (for example `overlay/README.md`) and executable-mode Markdown read only as Git text. The classification allowlist does not broaden: changed executable Markdown/templates/other paths still select runtime checks. This distinction catches an unchanged cross-module referrer when a prose target disappears.

Resolve link targets lexically against tracked Git tree entries; never read arbitrary filesystem links or out-of-repository targets. Support percent-encoded paths, Unicode/spaces and escaped parentheses. Root escapes, missing targets or symlink targets are broken. Read prose as strict UTF-8 from bounded Git blob batches; cap total prose data at16MiB and total helper work at30seconds. Resource limits or malformed input must not produce docs success.

Implementation ruling: cache unique prose blobs by Git OID across both revisions under the16MiB prose budget. Fixed per-blob reads may replace batch stdin to reuse the existing contained supervisor. Bound each command's captured output to16MiB and all observed Git stdout/stderr to64MiB, including tree/diff metadata; do not describe this additional metadata allowance as a16MiB total-output cap. Reserve cleanup time within the shared30second deadline. No unbounded in-memory command capture is permitted.

Parser refusal limits are explicit:4096 destination characters (including leading whitespace),4096 normalized/tree path characters,128 ancestor separators for an existing target,65536 characters per Markdown line, and100000 combined preprocessing line/backtick items per blob. Exceeding these limits refuses validation; do not silently truncate content or report docs passed. Check the shared deadline inside scans/preprocessing, including cases that produce no yielded link. Reference destinations cannot scan across an unterminated angle line repeatedly. Check absent targets before building ancestors; never materialize a quadratic list of joined prefixes.

## Helper interface

- `classify()` returns a JSON-compatible report with `mode` (`docs` or `full`), actual `head`, `base` when known, stable reason, and changed paths. It uses a fixed Git argument array; task/Markdown prose is never executed.
- `validate()` returns a successful typed report only for a classified docs change with clean whitespace and no newly broken supported local links; otherwise raises/refuses. It recomputes source facts.
- CLI `python -m task_tower.ci_docs --scope --report PATH --github-output PATH` writes mode to the Actions output file using fixed `mode=docs|full`; no untrusted content enters workflow commands.
- CLI `python -m task_tower.ci_docs --validate --report PATH --repository OWNER/REPO --pr N --phase pr|postmerge` produces `{version:1,kind:"documentation.validation",mode:"docs",head,base,repository,pr_number,phase,checks:"passed",runtime_tests:"not_run",validation:"whitespace_and_new_local_links"}` plus bounded diagnostic counts.
- `--report`/output are explicit caller-selected paths; workflow stores them under `runner.temp`, outside the clean source tree.

## Actions routing and truthful artifacts

A Windows scope job classifies actual source. Four existing runtime shard jobs depend on it and run only for `full`. Stable final check `unittest (windows-latest)` always runs: for `docs` it validates documentation; for `full` it requires successful full matrix and the existing exact-source/inventory checks. Failed scope, malformed mode or unexpected skipped/cancelled dependencies fail the stable gate. Do not use whole-workflow path filters that strand required checks Pending.

Postmerge scope, shards and final publisher all check out the actual merge SHA. For `full`, retain existing `pull_request.merged` runtime event and `task-tower-merge-<PR>-windows` artifact, emitted passed only after verified full matrix. For `docs`, validate source and publish **only** `task-tower-docs-<PR>-windows`, containing the typed documentation report above. Never emit a runtime merge-event or `runtime passed` claim when runtime tests were skipped. The legacy runtime consumer is not modified to invent acceptance for docs-only changes; canonical Beads closure remains coordinated after type-appropriate independent main acceptance.

Keep PR supersession cancellation scoped to its PR. No credential, permission, protection, model/account or platform changes. Code changes to this helper/workflows/tests are full-route changes themselves and require real Windows matrix CI.

## Acceptance

- Meaningful RED/GREEN regressions cover prose/mixed/workflow/template/mode classification; renames/deletions/odd filenames; missing history and single-parent ambiguity; baseline/new broken links, deleted targets, encoded Unicode paths/code blocks/anchors/external schemes and resource limits. No network or private filesystem traversal.
- Independent spec/buildability and whole-diff exact head/base reviews; all applicable real CI checks green; serialized expected-head merge; independent exact-main source plus full matrix/event acceptance for the implementation.
- Then a useful documentation-only results-report PR proves the live fast route: no runtime shards executed, stable checks successful, exact-main typed docs artifact verified and runtime artifact absent. Do not close `tt-qrk.2` before this pilot reaches accepted main.
# Evidence-driven Windows test environment amendment

PR79 CI41943924096 failed in two original native preparation cases. The bounded observer identified `PipelineJournal._wait_seconds()` line119, reached from `_db()` line199 before `sqlite3.connect` was called: the cancellation read's original one-second budget was exhausted. Successful containment/shutdown does not establish why preconnection wall time was consumed; filesystem latency and scheduler delays remain unseparated.

A fixed local profile of synthetic empty journals used three samples per layout and phase. Five additional ancestor levels increased `lstat` calls from96 to136; validated status calls took about4.8–7.8ms locally and all passed with the original one-second guard. This proves path-depth workload scaling, not hosted-CI latency, reproduction or a defect fix. Instrumentation and earlier samples can warm caches; the profile is separate from acceptance.

As a bounded workload-reduction experiment, only runtime shard test steps in PR/postmerge set TMPDIR/TEMP/TMP to `${{ runner.temp }}`. A preceding fresh-Python step uses the identical step-level environment, checks `tempfile.gettempdir()` against RUNNER_TEMP, fails with fixed path-free messages and prints numeric depth only. Temporary children remain unique and use normal cleanup. Scope/docs/aggregate steps, production checks, all test expectations/deadlines and artifact semantics stay unchanged. Parent bug `tt-qrk.4` remains open without a proven accepted fix; full current-head and exact-main CI are still required.

GitHub documents [runner temporary-directory lifetime](https://docs.github.com/en/actions/reference/workflows-and-actions/variables) and [context availability](https://docs.github.com/en/actions/reference/workflows-and-actions/contexts): runner is available in step-level env, not job-level env. Do not write GITHUB_ENV or use unsupported job-level runner expressions for this change.
