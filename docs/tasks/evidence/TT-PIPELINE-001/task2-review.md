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


## Current R2 integration extension review — accepted

Verdict: **accepted for Task 2 R2**, superseding R1 only for the four revised bindings below. Original rejection and R1 acceptance remain historical. Independent reviewer `/root/pipeline_journal_review`, source HEAD `020ef36e9e80639f1552f67676752a8cc9426b38`. Read ledger Rulings 12–13 and the accepted spec/plan mutation, history, recovery and preparation contracts. The additive extension is necessary to capture actual failed mutation for bounded rework and to hand off initial preparation between bounded worker invocations; it grants no normal acceptance or publication authority.

All four final frozen raw hashes equal their canonical UTF-8/LF hashes, independently verified before final report:

| File | Raw and canonical SHA256 |
| --- | --- |
| task_tower/pipeline_inputs.py | ad11e773f7564204edc58e0a080d9f667d657afa48997e07ef343e1214f8bc16 |
| task_tower/pipeline_journal.py | 61b82e11015130b9f443adeee7c38300a941e5b35925295cccc938541a18b43e |
| tests/test_pipeline_inputs.py | 0449de1a85aa3e8fe5e9e6c15a4d1d6976303f6dcfe8994ac07f5b0a2e605566 |
| tests/test_pipeline_journal.py | cce8849d345e22f8193a26b134f5f479035aedce3ecb7c611947afc73346d5f0 |

The originally supplied R2 input-test hash `5ec09261955f6ed0019bf0c0ec27200b0eb4d36870c8a8c6ebba6824b757fa85` is superseded and NOT accepted: its preexisting Cyrillic fixture had been mojibaked by an author encoding mistake. My first independent targeted run actually failed that canonical JSON fixture (92 tests, 65.258 seconds, one failure and one skip). The original UTF-8 literals were then restored and final freeze confirmed by the author. This was a test-source correction; product source hashes stayed unchanged. This report does not silently reinterpret that failure as a passing run.

Fresh independent command using the absolute bundled Python documented above: `-m unittest tests.test_pipeline_inputs tests.test_pipeline_journal tests.test_executor_queue tests.test_tasks -q`: **92 tests, 63.248 seconds, OK, 1 skipped**. This includes real Git failed executor/check mutation capture, fresh development rework, proof/owner/run exclusion, preparation identity negatives and actual initial worktree/dead-owner handoff. The author separately reports the additional policy-inclusive 109-test suite passing; that is author evidence, not this reviewer's claimed command.

Additional independent negative/fault probes used real Git repositories and the same actual failed mutation fixture, with injected exceptions around the new rework freeze. Before durable intent (at write-tree), no rework effect exists and the ref is unchanged. After durable intent (at commit-tree), exactly one unresolved intent remains, the ref is unchanged and another freeze is rejected. After actual update-ref returns but before observation, the ref has moved, exactly one unresolved intent remains and another freeze is rejected. All three probes passed. Separate hostile mutation-proof probes rejected an unstarted failed process, source_unchanged true and cleanup_confirmed false.

Code review confirms the same private index/hook-disabled raw Git implementation serves both freeze paths; failed_attempt_id is journal-validated against actual same-run/owner/input/generation/stage role and failed cleaned started process evidence. Rework effects require null normal contributor and no publication evidence, are one per failed attempt, and are excluded from the normal commit selection used by accepted verdicts. Failed-action readiness requires the linked positively completed rework commit, exact checkpoint, generation increment, stale_input and positive cleanup; test mutations target development and invalidate downstream acceptance through the existing bounded applied-rework protocol. Fresh target executor work is required. Unresolved effects cannot be resumed or replayed.

Initial preparing-to-ready is restricted to spec generation one, immutable admission/source/base, no attempts/verdicts, an owned matching positively completed worktree creation and an initial-source checkpoint with no prior verdict/check proof. It grants no review/publication passage. The real worktree/dead-owner handoff test establishes that an initial zero-process ready action can continue without replaying preparation. Task4 remains responsible for actual Git/external freshness immediately before recording transitions, as explicitly assigned by the accepted rulings; this review does not substitute journal-stored claims for Task4 verification.

No blocking Task 2 R2 findings remain. Builder check: **nothing important left within this extension boundary**. No product files, commits or pushes were changed by this reviewer. Final whole-controller/integration, publication, CI, exact-head/base PR and exact-main gates remain separate. Any change to the four bindings invalidates this acceptance.


## Current R3 narrow identity-guard review — accepted

Verdict: **accepted for Task 2 R3**, superseding the R2 four-file bindings while preserving the historical reviews above. Independent reviewer `/root/pipeline_journal_review`; source HEAD `ff7f39c889f891d2747de6fb56f418c171ceab20`. The author disclosed a further missing-identity case after R2: null stored worktree/Git-directory identities could match a worktree_create intent with null values and reach initial ready. Ruling 13 requires actual bound directory identities. This narrow correction closes that API gap rather than relying on the normal Task4 caller to always supply paths.

Final raw hashes equal canonical UTF-8/LF hashes, independently verified before and after checks:

| File | Raw and canonical SHA256 |
| --- | --- |
| task_tower/pipeline_inputs.py | ad11e773f7564204edc58e0a080d9f667d657afa48997e07ef343e1214f8bc16 |
| task_tower/pipeline_journal.py | 58bf6caf92ec9ba39d61f6e92914c0bfed5f3ea803c36ad8ce21201a8e89045f |
| tests/test_pipeline_inputs.py | 0449de1a85aa3e8fe5e9e6c15a4d1d6976303f6dcfe8994ac07f5b0a2e605566 |
| tests/test_pipeline_journal.py | c108186861c59874f49d2bb6267bf0b045c64b7cb8395cd2cf650976f7bf4013 |

Inspected the entire actual diff: three production guard lines and ten additive test lines. `_intent` now calls the existing strict host-directory validator for each worktree_create worktree/git_dir value before any effect intent can be persisted; `_initial_ready` independently requires both saved identities to be nonnull. Existing immutable bindings, actual source observation, no-attempt/verdict constraints, unresolved fencing and preparation/rework logic remain intact.

Independent public-API negative probes varied each directory field separately while keeping its counterpart valid: None, False, integer, relative path, Windows reserved-name path and an existing file path. All twelve combinations raised ValueError and the effect history remained empty. This verifies rejection occurs before effect persistence rather than merely rejecting a later ready transition.

Actual independent bundled-Python command: `-m unittest tests.test_pipeline_journal.InitialIdentityGuardTests tests.test_pipeline_journal.InitialReadyProofTests tests.test_pipeline_inputs.InitialReadyCheckpointTests tests.test_pipeline_inputs.ReworkCheckpointTests tests.test_pipeline_journal.ReviewRegressionTests -q`: **7 tests, 18.386 seconds, OK**. The positive actual Git initial preparation/dead-owner handoff and both failed test/check rework flows still pass; R1 late stale-reject and strict typed-preparation regressions also pass. The author separately reports 110 focused tests passing in 62.080 seconds with one skip; that is separate author evidence, not a broader suite rerun by this reviewer for a three-line change.

No blocking R3 findings remain. Builder check: **nothing important left within this narrow guard correction**. No product edits, commit or push were made by this reviewer. Task4's actual external/Git preparation validation and final worker-flow acceptance, later publication and CI/PR/main gates remain independent obligations. Changing any binding invalidates this acceptance.
