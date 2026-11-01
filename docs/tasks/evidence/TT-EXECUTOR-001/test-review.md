# Independent whole-Issue test acceptance — Issue #15

## 2026-11-01 final frozen-input review — ACCEPTED (local test stage)

Reviewer: independent executor_final_test instance, distinct from implementation. Reviewed current executor policy, adapter/CLI, queue, worker, harness/result contract, process/fault/integration tests, executor documentation and accepted Task 1–5 evidence. No production or test edits, commits or remote mutations were made. This is local test-stage acceptance, not exact-head/base PR or postmerge acceptance.

The reviewed worktree HEAD was `d8b3ea7e597bcb06eb951a442ae629773808c44e`, with integration changes not yet committed. Binding is therefore the frozen canonical source inventory: **1f2976d3ba36559408326f728a25a2c4eeee7ea0613d00ff6f79544185cc9bae**, **116 files**, identical before and after both suite runs and boundary probes. Inventory consists of `task_tower/*.py`, `tests/*.py`, root `README.md`/`AGENTS.md`, and `docs/**/*.md` excluding `docs/tasks/**` (mutable cards/evidence). Each file is decoded UTF-8 with optional BOM removed, CRLF/CR normalized to LF and hashed as UTF-8; aggregate hashes the path-to-digest mapping as sorted compact JSON. Raw runtime/logs are excluded. Inventory membership and all hashes were regenerated after the final suite; no additions, removals or changes occurred.

Bundled Python **3.12.14**, Windows 10 build 19045: fresh `python -m unittest discover -s tests -v` completed **429 tests in 100.448s, OK, 4 skipped**, exit 0 (425 executed tests passed). Skips: executor capture symlink, instruction-file symlink, harness state-directory symlink, postmerge database-parent symlink; each reports unavailable Windows symlink privilege. Separate junction cases executed successfully. No POSIX or future CI result is inferred.

Six independent temporary-fixture probes passed: changing the admitted profile timeout prevented preparation; a real custom child returning needs_input retained that state and was not replayed; a real zero-exit child returning a wrong source SHA failed; 1366 three-byte summary characters exceeded the 4096-byte result limit; unknown ownership consumed a one-slot capacity while queued cancellation remained cancelled; boolean Issue admission failed before creating a queue. The probe loader also reran 20 existing WorkerFaultTests, so its actual summary is **26 tests in 16.894s, OK**, not 26 new tests. Existing fault coverage independently inspected includes cancel before/after worktree and during a real child, unavailable/changed dependency evidence, claim and intent crashes, source/policy drift, ownership fencing, bounded retry history, strict malformed results and no-child proofs. No blocking defect found in these boundaries.

Historical reviewer harness correction: the first full run deliberately isolated TEMP but mistakenly placed it inside the enclosing Git checkout. Its readiness non-repository fixture consequently inherited the parent repository and failed; summary **429 tests in 107.739s, 1 failure, 4 skips**. The source was unchanged. Restoring the ordinary system temporary directory and rerunning the complete suite produced the passing result above. This environmental failure is preserved, not presented as a production fix.

Installed Codex evidence remains separately recorded in `installed-codex-smoke.md`; the trusted Python fixture does not prove installed Codex behavior. Authenticated production #14 receipt readability is a separate coordinator gate and is not supplied by synthetic remote receipt tests here. The historical capture/main evidence does not establish executor main acceptance. Current three-platform CI, independent whole-Issue development review, fresh exact head/base PR acceptance, serialized merge/postmerge acceptance and automatic Issue closure remain required. No night, daemon, event parser, resume, automatic publishing or unattended pool readiness is claimed.

Local raw log SHA-256 (logs remain untracked runtime evidence):

- `runtime-final-acceptor-suite.log`: `a9b20a79018639ae0ff6bc42320f396825d37c80be4b8b46f3c2e5bc244c6833`
- `runtime-final-acceptor-suite-default-temp.log`: `62d42bc2fafe3b5c2c21d04cf9ef5acf01daf9052d002f10b36f0efa88659350`
- `runtime-final-acceptor-probes.log`: `c5b03321ec82b1400b746b05609be300a5699fef8c3a3395f3c600e75cea0cad`

## 2026-11-01 updated-main/fixture supplement — ACCEPTED (local test stage)

Independent executor_final_test re-reviewed the frozen integration after main advanced to `f7ce385b89cdddda089985404ce11fffc36a0797`. This supplement supersedes the prior source binding, preserving its full-suite result and historical failure/correction. Regenerated membership and all canonical hashes before and after focused verification: **116 files**, unchanged within this review, aggregate **918e4bf14e57f35407259583c3ed8134ab6acd7c69f8f6a628fdd44288e60a1c** using the same inventory/encoding rules above. Exactly four inventory files differ from the previous binding; all production Python files and all other tests/docs are unchanged.

The two test files contain exactly three expression substitutions: `sys.executable`/`os.sys.executable` becomes `str(Path(...).resolve())` when supplying the reviewer-owned Python executable to integration/worker fixtures. No assertion, production guard or invocation policy changed. This accepts the real interpreter path on installations whose executable traverses a symlink, consistent with the existing queue/temp-path fixture treatment; it does not authorize raw aliased production configuration. Independent Windows junction probe created an executable-directory alias: raw aliased executable was rejected by real `load_executor_config`, and resolving that fixture executable succeeded. The junction was explicitly removed before fixture cleanup. POSIX execution is still established only by current platform CI, not this Windows probe.

The only changed docs, `docs/development-process.md` and `docs/session-capture.md`, add the exact standalone task marker/head-base mapping gate and explain same-Issue reviewed recovery for the omitted capture merge-event identity. They preserve genuine unbound event history and prohibit fabricated receipts, journal resets or manual closure as substitutes. They do not modify executor behavior or weaken serialized postmerge acceptance. No blocking finding.

Fresh independent command `python -m unittest tests.test_executor_integration tests.test_executor_worker tests.test_executor_profiles -v`: **44 tests in 22.521s, OK (1 unavailable symlink privilege skip)**, exit 0. Combined with the prior complete 429-test result and verification that all production and remaining tests are byte-equivalent canonically, this is sufficient for this narrow local test-stage supplement; no redundant second full run is claimed. Changed file canonical hashes:

- `docs/development-process.md`: `c0a5cdb73ceb45b855064e408e9f2ecb55ff520b76cd83b079cd05a3a54a09c9`
- `docs/session-capture.md`: `dea1a154d545ef99f7c393d27d1be8e5d5c7ed26e69044e5303c4788ee73c822`
- `tests/test_executor_integration.py`: `01964a00cd94172a95a8960dbaf369de89ad6cff36f24b8c1d30ced1bb790740`
- `tests/test_executor_worker.py`: `9f9ab044a602084aec74bd93b072e285d952bbd2eff619fab15893e9d8b9ad2a`

Focused log SHA-256: `722a4338733e1bf599ce039fec16f42ab3f8bd4a6d964f115a05389c36383f69`. Current all-platform CI, fresh exact head/base PR acceptance, exact-main postmerge acceptance and automatic Issue closure remain separate. No source/test edits or commits by this reviewer.
