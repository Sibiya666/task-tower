# Independent installed-Codex V2 evidence audit

Reviewer `/root/books_native_smoke_impl`, 2026-11-02. **Verified positive six-role/three-stage/check evidence; full end-to-end Task7 goal remains BLOCKED at final publication validation.** The preserved run did not reach `ready_for_pr`. This is not live GitHub, PR/main acceptance or unattended readiness.

## Exact preserved evidence

Pilot source HEAD `25be4657bbf5812dd2029c23b6b7c3f0aab93e06`. Sanitized report SHA-256 `bfb1fc18ea96214a7126ebf2f9ff4184388e13396e745ecb33b049cb06a3a5f8`; evidence-manifest SHA-256 `0b1ca655cd42c77de63721613075cb91455d41730774460427ffed871403525e`. Independently checked all **445** file hashes and sizes. The earlier negative pilot's **166** bindings also still match manifest `9a7fc9bacca52fc945721f74235b58e5fcced380e1435d8fbc00d6e440aaddda` and report `f95bc5f62ca3e4006c7e8ee7f56646d7bbb8e217fa382751c2ef9d4788b23067`.

Independently compared 22 preflight source canonical bindings against actual Git blobs at the exact pilot HEAD, rather than comparing them to the subsequently corrected uncommitted blob reader. All match. Eight private preparation/check/config bindings remain unchanged. No raw prompts, credentials or absolute private worktree paths are reproduced here.

## Positive installed-role and check findings

All six actual role requests/results pass the production strict schema and exact run/attempt/instance/stage/generation/source/checkpoint/input binding validator. Saved schema hashes match the generated schema; request stage-manifest digests match bound input hashes. There are six distinct host-generated instance IDs and six recorded Codex thread IDs, not a resumed role. Read-only SQLite inspection confirms seven completed attempts: six model roles and one configured host check, with three unsuperseded approve receipts for spec/development/test.

| Actual role | Duration | Exit / cleanup | Observed / saved stdout bytes |
| --- | --- | --- | --- |
| spec executor |76.296s|0 / confirmed|63930 / 63930|
| spec reviewer |34.765s|0 / confirmed|54762 / 54762|
| development executor |45.344s|0 / confirmed|81553 / 65536|
| development reviewer |29.687s|0 / confirmed|45031 / 45031|
| test executor |46.984s|0 / confirmed|55493 / 55493|
| test reviewer |36.407s|0 / confirmed|50669 / 50669|

The development executor stdout is **explicitly truncated** to the configured 65536-byte prefix; its observed count is81553 and tail_unknown is false. The saved prefix hash/size is independently verified. The full-stream digest is a runner observation and cannot be independently recomputed from the saved prefix. Other complete stream hashes/counts match the artifacts. There is no claim of a complete development transcript. Required structured results and bindings were preserved separately and validate.

All six roles have matching raw recorded ASCII-escaped reader command events: counts2/2/2/2/4/4 respectively, including start/completion events rather than sixteen extra roles. This supports actual use of the corrected reading guidance; it does not prove every model interpretation was correct. Reviewer/test-executor product-unchanged proofs remain true; permitted spec/development changes are separately recorded.

The fixed host check actually ran, passed with exit0/confirmed cleanup and unchanged source in0.250s. Its command-policy digest matches the saved private check. The immutable fixed-check file SHA-256 is `49648c22d07b70e07fdfb39b981fa92d69d9c6bc00f63441aa9e0da2312e6b04`. Model prose did not substitute for this check.

## PID, bounds and shutdown evidence

Eight raw read-only Codex-named process snapshots match the reported active attempt/instance, timestamp interval and ancestry to the saved host owner. There is one primary observation for each role; development has two additional descendants (ancestry depths2 versus its primary depth1), which are **not counted as additional roles**. Current positive OS-death checks pass for all eight observed PIDs, the saved controller and last host owner. This is distinct from the journal's cleanup attestations; outer PID death alone is not used as proof of child cleanup.

The operator stopped on the first parked state after367.250s with exit0. Policy bounds remain one active task, 1200-second task budget, 180-second role budget, twelve managed processes, zero reworks and 65536 bytes per captured stream. Process count7 fits that bound; no rework occurred. Controller health is stopped with workers0/dispatcher0. There are zero unresolved attempts/effects. These are bounded observed outcomes, not a service/night guarantee.

## Preserved final blockage

The journal remains `needs_input / test / environment_unavailable`, generation7. Five effects are completed: worktree creation and four checkpoint commits. Final host evidence exists at checkpoint `532880fd0b9ff63db98ded1277b4e62c1c0ea83e`: one1485-byte Markdown projection, SHA-256 `80b2783b446c5587ca3263642626e726b565856aaff0ccff7083dc6f49d51251`, manifest digest `0c9e272bcb41dc6466efecf9b1294490feceab9d6485def11e7df1e62ea3fcda`.

The old implementation failed when reading that completed blob through ambiguous `git show SHA:path` in a long Windows cwd. The original failed validator/filename-too-long evidence remains intact. Publication was disabled; no push/PR effect or external repository write occurred.

The independently reviewed typed-blob correction now validates the preserved object read-only, including current parent/tree/message/files/content bindings. I verified that the journal bytes and parked state remain unchanged. That observation does not execute a transition, replay an effect, authorize a reset, or convert this V2 pilot into end-to-end success. A new separately authorized experiment must establish any later `ready_for_pr` claim.

The first pilot's encoding-related rejection and missing role-PID evidence remain historical; this V2 evidence neither erases them nor attributes the earlier unrelated Task6 unknown to either failure. No new installed-model role, reset/resume/retry, private-journal mutation, source edit, settings change, commit, push or external write was performed by this reviewer. Full repository/current CI and independent whole-branch/PR/main/postmerge/closure gates remain separate.
