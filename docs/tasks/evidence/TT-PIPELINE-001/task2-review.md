# Task 2 independent review

Verdict: **rejected**. Fresh independent reviewer `/root/pipeline_journal_review`; source HEAD `1bc1aa44eebd6a0ccaf8c3be36427d49bd925c9d`. This reviews the four uncommitted Task 2 files, not a PR/main acceptance. No product file was changed by this review.

Accepted design canonical SHA256: `8de84fe1a6ea7e22f104a2b5812e86bedea97c9363cf0971bbbea5eba0fd0f77`; plan `4f13c9eb4bf4222a1cdebf5c677b7ed932d8415f386ee9623ade02906b916feb`. Read repository AGENTS, accepted Task 2 interfaces, current spec review and implementation ledger rulings 1–6. Inspected complete inputs/journal sources and corresponding tests.

## Frozen input bindings

All four raw hashes matched the coordinator freeze. Canonical means UTF-8 with CRLF/bare CR converted to LF, with BOM preserved.

| File | Raw SHA256 | Canonical SHA256 |
| --- | --- | --- |
| task_tower/pipeline_inputs.py | 3ef56a009f1d1b4ef4e44e14252ffffba8b782d58dac22f4288b6868563309b6 | 3ef56a009f1d1b4ef4e44e14252ffffba8b782d58dac22f4288b6868563309b6 |
| task_tower/pipeline_journal.py | 20333f3e3c3c1332da5ca47a49b1a677f206ec89908b0619ef7d04b7185206e4 | 20333f3e3c3c1332da5ca47a49b1a677f206ec89908b0619ef7d04b7185206e4 |
| tests/test_pipeline_inputs.py | d2a8718add26483188275831c5b20ba90f0e9532dbeff6177937aed83bd2a7c3 | 9a0a0980c9724381a4942206479e6b1295a21b2de000a2e063e0e49e0bc1a4dc |
| tests/test_pipeline_journal.py | 096c0751ed78e547f296f2bf2dca0050c2bc0037b8f62c86b920c5fc47108c7e | 98f5558ff1321036a1374e3ca375651292aaa621ff8b7e021beaa450b03d5bb9 |

## Blocking finding

**P1 — stale rejected history fences a valid replacement executor** (`pipeline_journal.py`, `_contribution_floor`, lines 465–466). The function applies every rejected receipt timestamp as an effective return boundary, including old-input rejects stored with `superseded=True`. Independently reproduced through public journal methods without database edits: finish old spec executor and reviewer; reset with stale_input and new generation; start the replacement executor; persist the genuine old reviewer reject; finish replacement executor; create its output checkpoint. The stale receipt correctly returns `superseded=True`, but the new checkpoint fails with `ValueError('Executor precedes rejection')`. This gives historical-only evidence control over current work and prevents forward progress, contrary to Ruling 4. An effective reject must remain a boundary even though genuine current rejects are themselves marked superseded; simply filtering all superseded rows would weaken rework fencing. Preserve a durable distinction between actually-applied rejects and merely stale observations. Add this order-sensitive negative regression plus the existing effective-reject recycling regression.

## Additional finding and future seam

**P2 — strict preparing identity validation is incomplete** (`record` / `_validate_db`). Independently submitted and claimed a fresh row, then called record with `{state:'preparing', issue_id:True}` and no admission. It succeeds and returns integer `1` after SQLite coercion. This violates schema-validated transition/Boolean-not-integer intent and can prematurely freeze a wrong immutable ID. Validate the optional identity before binding SQL, rather than relying on SQLite. The authoritative admission and action gates still prevent this alone from fabricating accepted execution; severity is lower than the stale-reject blocker.

The author-described PR observation limitation is a bounded Task 5 seam: `_neutral` currently rejects arbitrary URLs, and generic finish_effect does not yet require an actual typed PR observation. Do not claim awaiting_pr integration complete until Task 5 adds exact host PR identity/head/base/URL observation validation and its history gate. Task 2 rejection above does not depend on demanding unfinished Task 5 networking now.

## Actual independent verification

Used `C:/Users/sibiya666/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe` from the reviewed checkout. Actual command `-m unittest tests.test_pipeline_inputs tests.test_pipeline_journal tests.test_executor_queue tests.test_tasks -q`: **83 tests, 33.599 seconds, OK, 1 skipped**. Independently ran inline Python SHA256/raw/canonical probes and the two public-API negative probes described above. The targeted suite passes while the newly discovered stale rejection order fails, so green tests do not resolve this finding. The coordinator-reported larger suite is separate evidence, not rerun or claimed by this reviewer. Real Git/OS Python 3.11 CI remains a later independent integration gate.

Review examined v2 BOM-preserving/raw hashing, artifact/product caps, complete path/mode snapshots, unsafe aliases/links/Git environment filtering, private index and effect-before-commit/ref ordering, owner/PID/ready handoff, unresolved intent fencing, role/check/history and contributing executor bindings. No alternative mutable-card/model-summary authority was accepted. No source fix, commit or push was made. Fresh review of changed frozen inputs is required after correction; this verdict grants no implementation acceptance.


## Current R1 re-review — accepted, supersedes original rejection

Verdict: **accepted for Task 2**, by the same independent reviewer after examining the correction and independently reproving both findings. The original rejected review above remains historical evidence. Source base remains `1bc1aa44eebd6a0ccaf8c3be36427d49bd925c9d`; the accepted spec/plan and ledger rulings remain unchanged. This is neither final Issue/PR/main acceptance nor a claim of completed Task 5 publication.

Fresh frozen bindings, independently computed on disk:

| File | Raw SHA256 | Canonical UTF-8/LF SHA256 |
| --- | --- | --- |
| task_tower/pipeline_inputs.py | 3ef56a009f1d1b4ef4e44e14252ffffba8b782d58dac22f4288b6868563309b6 | 3ef56a009f1d1b4ef4e44e14252ffffba8b782d58dac22f4288b6868563309b6 |
| task_tower/pipeline_journal.py | 960b0efa4c15263b9b559c3145f42b1916baad6e55206cf9954b03d93bad8448 | 960b0efa4c15263b9b559c3145f42b1916baad6e55206cf9954b03d93bad8448 |
| tests/test_pipeline_inputs.py | d2a8718add26483188275831c5b20ba90f0e9532dbeff6177937aed83bd2a7c3 | 9a0a0980c9724381a4942206479e6b1295a21b2de000a2e063e0e49e0bc1a4dc |
| tests/test_pipeline_journal.py | 7cf31b41e7b13a0c5355bdad309ca8313372491ca3521cb68ed073f9e5c8a3c0 | 7cf31b41e7b13a0c5355bdad309ca8313372491ca3521cb68ed073f9e5c8a3c0 |

P1 is resolved through durable journal-owned `rework_applied` events carrying target stage and generation floor. Only an actual current reject or accepted stale-input reset creates an applied boundary; a late stale receipt remains immutable superseded history. `_contribution_floor` consumes applied generation boundaries rather than every rejected receipt timestamp. Actual reject events link the receipt ID. This preserves effective historical returns even after their verdict rows are superseded, and removes wall-clock ordering as the contribution decision.

Independently replayed the original failing public-API sequence: old completed reviewer reject arrives after replacement executor launch; save returns superseded true; replacement completes and checkpoint succeeds with ready state. Separately exercised a genuine current reject and then attempted another checkpoint from its old contributor **without starting any later executor**. This still fails with `Executor precedes applied rework`, demonstrating the rework gate itself remains effective independently of the latest-attempt gate. Existing fresh contributor, ready resume/dead PID/unresolved intent and host check tests also pass in the suite below.

P2 is resolved by strict pre-SQL validation of optional Issue ID, SHA bindings and absolute safe host directory fields, plus named neutral evidence UUID/hash/count/Boolean/process fields. Independently tried twelve bad inputs: Issue ID True/string/zero/negative/float/None, Boolean PID, string generation, malformed attempt UUID, negative byte count, integer source_unchanged and Boolean exit_code. Every input raises ValueError and leaves the originally null Issue ID unchanged. No authoritative identity is produced by SQLite coercion.

Actual fresh independent command, using the same absolute bundled Python path documented above: `-m unittest tests.test_pipeline_inputs tests.test_pipeline_journal tests.test_executor_queue tests.test_tasks -q`: **85 tests, 40.286 seconds, OK, 1 skipped**. This is the exact command/count run by this reviewer; larger author/coordinator suites are separate evidence. Independent inline hash and negative probes also passed as described. No product changes, commit or push were made by this reviewer.

No blocking Task 2 findings remain. Builder check: **nothing important left within this reviewed Task 2 boundary**. The known typed PR observation/URL extension remains explicitly owned by Task 5 and must be independently checked before any awaiting_pr integration claim. Subsequent source changes invalidate this Task 2 acceptance. Whole-implementation testing, three-OS CI, final independent development/test acceptance, exact head/base PR acceptance and exact-main postmerge acceptance remain separate gates.
