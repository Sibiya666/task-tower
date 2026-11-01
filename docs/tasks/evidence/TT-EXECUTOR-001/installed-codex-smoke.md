# Installed Codex harness smoke

The coordinator requested a bounded real installed Codex run against a private scratch Git worktree. This is genuine harness/process execution, separate from fixture-based Issue transport in integration tests. It does not prove real Issue authorization, stage transitions, event parsing, resume or unattended readiness.

Installed version: `codex-cli 0.166.0-alpha.5.1`. Outcome: exit `0`, validated `completed`, exact marker `True`, cleanup confirmed `True`, duration `24.719` seconds.

Fixed invocation: `exec --json --sandbox workspace-write --output-schema PATH --output-last-message PATH -C WORKTREE PROMPT`. No model selection, full-auto, bypass or approve-for-me flag. Both GitHub token environment keys were removed. Each stream was capped at 64 KiB; neither truncated. Existing CLI authentication was reused.

Superpowers actual clean Git revision: `bb92a77741419a4ab5f06e711a283343f1ada0c3`; canonical instruction manifest `5f0164e9d4fcdc8e6892aadc1774a7c5a3cce66e6db5586522a4dc02b6ccdd4d` validated and snapshots supplied. This proves those installed bytes, not trust in arbitrary unmanifested files.

| Evidence | Value |
| --- | --- |
| run_id | `1d6512b9-8817-4bf6-9ab2-40a92ba782d2` |
| attempt_id | `3cac9954-fdc2-4eb2-b434-0bf543518db3` |
| source_sha | `45ce2ebaddd1da6edc2bede4736b6961811e1a27` |
| request.json_sha256 | `0b86c29822adb2bbecbbe4846f8015d13115a296af9eccd4b339dbb78e61c381` |
| schema.json_sha256 | `723009b2c9f2ded5536c7fef0cc795d748746cbc01f33c1e7c0766f0a9e82c7b` |
| result.json_sha256 | `1cfb75608c465053dc4621ad180a6c50330975e3a2c31815e71d7fe59881541c` |
| provenance.json_sha256 | `0ad841f3148428b1b94c4d5e25492ad1af2d06480b1a7cc28996eaa80373d1c0` |
| stdout_bytes | `28926` |
| stdout_sha256 | `ba827ab8d15f045195eb81b4beddbdeadc8f1dbce24165b3812a54952cb24095` |
| stdout_truncated | `False` |
| stdout_tail_unknown | `False` |
| stderr_bytes | `7727` |
| stderr_sha256 | `eb584aeb8e296d3efc59f537e2db2d6bfbdc1c6cb99e92af9d31b8f03c8c8341` |
| stderr_truncated | `False` |
| stderr_tail_unknown | `False` |
| Private report SHA-256 | `c399de2e1b7776603e244236d622ca311bf08c856874fe83060b0f3a364f2e9c` |

Raw prompts, absolute installation paths and logs remain private installation evidence. Runtime capability reporting remains conservative: this recorded smoke is not persisted as a generic claim that future installations or profiles are verified. Independent task, whole-Issue, PR and exact-main acceptance remain required.
