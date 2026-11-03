# Existing pipeline fixtures: macOS temporary-path correction

Fixer `/root/pr_reviewer_review`, 2026-11-02. This is an author fix report requiring separate coordinator acceptance, not self-acceptance. Scope is seven positive fixture-path replacements across three test files. No production changes, skips, predicate substitutions or weakened negative assertions. Task6 author retains tests/test_pipeline_cli.py; that file was not edited here.

## Observed RED and cause

Fetched actual GitHub job125015394586 logs for run41362407458 (head6ff8597): macOS ran591tests in320.000s, FAILED(failures=3,errors=48,skipped=6). Pipeline journal setUp line19, input roots/checkpoint journals and role result paths failed deliberate safe_config_path checks with `ValueError: Unsafe connections path`. The size_limit test instead saw unsafe-path failure; initial actual ready subprocess likewise failed before its semantic assertion. macOS lexical `/var` temporary paths include a symlink ancestor. Canonicalize positive fixture roots before passing them into strict guards; preserve production rejection of aliases.

Seven corrections: one journal root, five input roots (repository, three checkpoint journals and external index fixture), and one role-protocol result root. Intentional hardlink, symlink, outside-allowlist, Git-index redirection and size-limit arguments/assertions remain intact. The existing Task6 journal test edits were preserved; the only additional line there adds `.resolve()` to its positive fixture root.

The same remote job also reports executor_queue competing processes outcomes `['', 'True']` versus `['False', 'True']`. Its positive roots already resolve; logs omit child stderr/return codes for that failure. No evidence establishes that separate failure as this path bug. Queue source/tests remain untouched by this fix; local queue tests are included below as a compatibility check, not a remote-race resolution claim.

## Frozen test content

| File | Raw SHA-256 | Canonical LF SHA-256 |
| --- | --- | --- |
| tests/test_pipeline_inputs.py | `3520123760ad8902722ecb5e59d237116237d7b0cbff06d776e98002a083f791` | same |
| tests/test_pipeline_journal.py | `a8b43dc8576bacb04bb19885294c3995d1bcc952ae5b5f26293924a05e0b3115` | same |
| tests/test_pipeline_roles.py | `dd6d4c53f529b816b00b8aa703dcc26c5837728438cce31fef28d3e6b664beab` | `54bf652a0924e8a6416a37a805d461cfe2822994067c93cfeda525b10eb6138c` |

## Local verification

Absolute Python: `C:/Users/sibiya666/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe`.

```text
python.exe -m unittest tests.test_pipeline_inputs tests.test_pipeline_journal tests.test_pipeline_roles tests.test_executor_queue -v
```

Result: **105 tests in 119.567s, OK (skipped=1), exit0**. The single existing skip is POSIX executable-mode transition on Windows. The actual competing queue claim test passed locally; this does not establish the separate remote failure's cause or resolution. No local macOS execution is available; remote three-OS rerun remains required. No full-suite, installed Codex readiness or successful remote CI claim. No commits/pushes or live external writes.
