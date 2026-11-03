# Independent Unicode reading-guidance review

Reviewer `/root/books_native_smoke_impl`, distinct from the implementer; 2026-11-02. **ACCEPT the exact two-file correction below.** No blocking findings remain within this scope. This is implementation review of reading guidance, not success/acceptance of the blocked installed-model pilot or permission to launch another model.

## Exact bindings and scope

HEAD `ebfd05909735c43d581f0e71a0462d556b23e81d`; supplied base `918554a1e7f6dec10f81a366c1dececa845ff072`. Freeze `runtime-task7-unicode-freeze.json` SHA-256: `272e024636e77480bfe3ab839afe107ceb51d3467b126316bdf90735022a092c`.

| File | Raw SHA-256 | Canonical SHA-256 |
| --- | --- | --- |
| task_tower/pipeline_roles.py | `15422eae2391db22d5ce8905337166736470eca6d5f13250e026c12d2d7507b9` | same |
| tests/test_pipeline_roles.py | `877505600d01cc88dfbccd3340d9aee4128525c929f83e0db7b507b050061ece` | `6ed42ce28811b848c8d044807a914c59f18db3e4939d460cf2a44ae81a8d2dda` |

Independently verified both raw/canonical bindings before and after checks. The other 20 Task6 R2 manifest bindings remain unchanged. Reviewed the entire actual diff against the accepted spec/plan role obligations and the independently audited byte-versus-console pilot evidence.

## Assessment

The production delta imports `sys` and adds shared agent-facing obligations for all six roles. Before acting on a Unicode-dependent requirement/finding, roles must inspect actual UTF-8 source through an ASCII-escaped JSON or byte/code-point view. The example uses the existing resolved host Python interpreter, passes the affected source path separately, reads strict UTF-8 and emits `json.dumps(..., ensure_ascii=True)`. It installs nothing and does not rely on a model inventing a new interpreter. Optional UTF-8 output is limited to the current command/process; global environment, OS, authentication, home, model and sandbox changes are explicitly prohibited.

This addresses a demonstrated inspection-channel loss, without altering source bytes or telling a reviewer to approve/ignore a finding. The preserved common host-policy/untrusted-data obligations remain first, and the existing role-specific spec-only/product-path/read-only/evidence restrictions remain intact. The generic reader example does not grant access to unrelated files or extend the saved allowed-path/installation authority. It is reading guidance; source authority, invocation/sandbox flags, token stripping, role/result schema, checkpoint/provenance validation and independent verdict gates are unchanged.

The example is appropriate for affected UTF-8 text; it is not a new binary decoder or execution mechanism. ASCII-escaped output preserves sharp-s, em dash, Greek and supplementary-plane emoji independently of console representability. Review authority still comes from independently validated bound results and host evidence, not appearance of the example in a request.

## Independent verification

Used absolute Python `C:/Users/sibiya666/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe`:

```text
-m unittest tests.test_pipeline_roles tests.test_executor_harness -v
```

**37 tests in 64.393s, OK, exit0.** Independently ran the actual supplied reader snippet in a real subprocess forced to CP866 output: ASCII-only output decoded to the exact original sharp-s/em-dash/Greek/emoji text. All six real custom-fixture role subprocess requests contained the shared guidance while retaining their distinct stage obligations and genuine journal bindings. These are trusted local fixtures, not installed-model execution. Authority/policy tamper, reviewer mutation, token removal, unknown cleanup, no-replay, strict schema and legacy v1 harness regressions also passed. Scoped diff whitespace check passed.

Read the author's preserved RED evidence: two tests produced seven expected failures before implementation (six missing-role obligations and no executable snippet). The independent GREEN above is distinct from the author's 37-test 65.094s run.

## Preserved negative pilot and limits

Rehashed every one of the original 166 private evidence entries before and after this review; all remain unchanged. Original report SHA-256 `f95bc5f62ca3e4006c7e8ee7f56646d7bbb8e217fa382751c2ef9d4788b23067` and manifest SHA-256 `9a7fc9bacca52fc945721f74235b58e5fcced380e1435d8fbc00d6e440aaddda` still match. That pilot remains two roles, rejected/parked at spec, with no six-role or host-check success. Missing historical role PIDs are not invented. The earlier unrelated Task6 unknown remains unproven.

No new installed-model role, reset/resume/retry, private pilot change, source edit, commit, push or external write was performed by this reviewer. Any new installed pilot still needs Root authorization and separately bound evidence. Changed reviewed inputs invalidate this verdict; full repository/CI, Task7 pilot, whole-branch/PR/main/postmerge and Issue-closure gates are not supplied here.
