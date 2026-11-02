# Installed Codex negative-pilot evidence audit

Independent reviewer `/root/books_native_smoke_impl`, 2026-11-02. **Task7 six-role installed-Codex goal: BLOCKED.** The evidence supports a narrower positive finding: two actual installed-model roles completed their bounded protocol exchange, a real reviewer rejection parked the run, and the operator stopped cleanly. This is not six-role success, stage approval, live GitHub integration, pilot acceptance or unattended readiness.

## Exact evidence and independent checks

Product HEAD: `ebfd05909735c43d581f0e71a0462d556b23e81d`. Private sanitized report SHA-256: `f95bc5f62ca3e4006c7e8ee7f56646d7bbb8e217fa382751c2ef9d4788b23067`. Private evidence-manifest SHA-256: `9a7fc9bacca52fc945721f74235b58e5fcced380e1435d8fbc00d6e440aaddda`. Preflight SHA-256: `48cc25142c04aa8ced61714d0dbb69aa52077467ff2c9db4bfa9da239b0b51a0`.

Independently read and hash-checked all **166** manifest entries, including byte counts; all match. The manifest binds the report. All 21 preflight product bindings and eight private preparation bindings still match. Both actual request bindings equal their corresponding result bindings; stage-manifest digests equal the bound input digests. The actual saved schemas equal `role_result_schema`, their hashes match, and the production `validate_role_result` accepts both exact result files. Task data is labeled untrusted in both requests. Distinct attempts, host-generated instance IDs and recorded Codex thread IDs support two fresh role invocations; there is no resume claim.

Installed version recorded: `codex-cli 0.166.0-alpha.5.1`. Pinned instructions record 60 files and manifest digest `1db765e99a5f991df69b15799e79862ef991001f136ab70f644f0187df940098` at revision `bb92a77741419a4ab5f06e711a283343f1ada0c3`. This audit verifies preserved evidence, not an additional model run.

| Actual role | Outcome | Duration | Exit / cleanup | Capture bytes stdout / stderr |
| --- | --- | --- | --- | --- |
| spec executor | completed | 79.266s | 0 / confirmed | 53969 / 6169 |
| spec reviewer | reject, return to spec | 36.422s | 0 / confirmed | 52347 / 5808 |

Capture hashes/counts match the raw files; neither stream was truncated or had an unknown tail. Each is below the configured 65536-byte per-stream cap. Role durations are below the 180-second role limit. The operator lasted 147.484s, below the 1200-second task budget; process count is 2 of the configured maximum 12. `max_reworks=0` made the first reject exceed the allowed returns: the saved result is `needs_input / spec / rework_limit`, generation2, spec rework count1. There are no approved stage verdicts. The four development/test roles and fixed host check did not run.

## Rejection and cleanup

Read-only SQLite inspection independently confirms two completed attempts, one preserved rejected spec receipt, and completed worktree-create/checkpoint-commit effects. There are zero unresolved attempts/effects and no push/PR effect. The operator stopped on the first parked outcome with exit0; that is a valid parked-tick result, not Task7 success. Controller health is stopped with workers0/dispatcher0. Read-only OS owner checks positively report the saved controller and last host owner dead. No journal reset, resubmit, retry, rework-limit change or source repair was performed by this audit.

The HTTP source/transport is a fixture, while the two role programs are the installed Codex executable. This establishes an installed process/protocol negative smoke, not a live GitHub Project/Issue pilot. The original failure and raw private artifacts remain preserved.

### Role PID limitation

The saved role proofs retain started/exit/cleanup/duration and stream/request/result hashes but omit the runner's role PID. Controller/host-owner PIDs are different evidence and cannot substitute for missing role PIDs. No retrospective role PID or individual role OS-death observation is invented.

The accepted Task7 plan requires six fresh instances, input bindings and process/cleanup outcomes. The accepted role-result and journal protocols use host-generated instance/attempt bindings and launch/cleanup evidence; they do not explicitly require a persistent role-PID field. Therefore this is an **audit-evidence limitation**, not by itself a demonstrated violation of the accepted result schema. It prevents a stronger retrospective per-role OS-lifecycle claim. The six-role requirement is independently unmet regardless.

## Unicode observation and read-only diagnosis

The preserved UTF-8 spec contains the expected sharp-s character U+00DF in its synthetic normalization example. The actual spec SHA-256 is `14780674856045aaf8d3df49f1e239072a26b578e22c688d87a767abc410bcf8`. The selected source-example line SHA-256 is `b4991249a1bc9e6aa40d611900de4353fca63964a0900a91ef64140f3867a367`.

Independently parsed actual recorded reviewer command events show `Stra?e`, including the second command with explicit `Get-Content -Encoding UTF8`; neither recorded example line contains U+00DF. Both recorded lines have SHA-256 `f371a9d9a6feaec3a160574e03b6bbd1396adbe4f003a0a6160e16384fa2db7e`. Thus the recorded as-seen example differs from the source bytes, and that example-based rejection is not supported by the preserved UTF-8 artifact. This does not retroactively approve the whole specification/plan or erase the reviewer's separate findings.

Root authorized read-only diagnostic children, not new model roles. Using the production contained process runner in the normal user context, with the exact installed shell executable and its recorded `-Command` prefix, I held the UTF-8 read constant and changed only per-process stdout encoding:

| Read-only diagnostic | Output code page | Known word bytes | Stdout SHA-256 |
| --- | --- | --- | --- |
| exact installed shell, default output |866| `53 74 72 61 3f 65` (`Stra?e`) | `5d5d0d49f7f829d0663e55b9e36b18d380c8d13ab0ab5b1b20f84a57b1ef19bc` |
| same shell, process-local UTF-8 output |65001| `53 74 72 61 c3 9f 65` (U+00DF preserved) | `ec114db37cfc753fc629800f8fdcf3ab514c84cb6f007fa29cd97b674f949c78` |
| Python UTF-8 read, `json.dumps(..., ensure_ascii=True)` |ASCII bytes| `\u00df`, exact decoded round trip | `2fd22184a4d0d9aa34b228376444098c655bb74a5a7271e2cbabba473da6f1b1` |

All three diagnostic children exited0 with cleanup confirmed. Windows PowerShell5.1 produced the same two shell-output digests in a preceding approved comparison. The exact-shell probe demonstrates a reproducible stdout-encoding loss after a correct UTF-8 read. The historical role did not record its console code page, so this is not proof of every historical lower-level hop. No persistent console, account, OS, security, authentication or model setting changed. The original report/manifest hashes remain unchanged after diagnostics.

## Minimal next proposal — not implemented

Before any new model pilot, review narrow cross-platform role guidance: inspect UTF-8 artifacts through an ASCII-escaped JSON/code-point view, and verify original bytes before a Unicode-dependent finding. Python's `read_text(encoding='utf-8')` plus `json.dumps(..., ensure_ascii=True)` is a demonstrated option; on Windows a process-local UTF-8 console-output setting is another. Neither requires global settings or security changes. Guidance must not suppress independent rejection or grant stage approval.

Any prompt/product change needs its own exact-input review and verification. Any subsequent pilot requires explicit authorization and a separate preserved identity; do not reset this parked journal or present a retry as the original success. Optional future observational PID capture would improve audit evidence, but is not silently added to the current schema or claimed retroactively. The previous unrelated Task6 R1 unknown remains unproven and is not attributed to this encoding observation.

No raw prompts, credential values or private worktree paths are reproduced in this public audit. No source changes, commits, pushes, additional model roles or external repository writes were performed by the reviewer.
