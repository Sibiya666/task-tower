# Issue17 CI capture path correction (pending independent review)

Baseline: 76669dcee250ce22b4137764de0237f41df908ab. Original CI41609618514 macOS failure retained unchanged in `runtime/ci-prworker766-failed.log` (SHA256 28ff7c295fac89fac1d09cf6c43ee7704a3ad1c9447aa14932e0ba6a2f8ff319). Windows/Ubuntu passing does not establish current macOS success.

## Root cause and ownership boundary
All 15 macOS error stacks terminate at pr_evidence._git -> pr_source._git -> processes._capture_files. The new helper creates TemporaryDirectory via the OS default temp root, passes raw Path(directory), then Source creates a capture child. macOS temp roots commonly spell /var through a symlink ancestor; strict capture correctly refuses that raw ancestry. The dependent provider assertion fails before provider invocation at the same bound Git check.

Only the exclusively host-created temporary directory is now resolved(strict=True) before passing to the unchanged Source Git helper. Caller root, caller output directories, Source transport, Source capture creation, capture link/reparse/collision checks, schemas, profiles and public legacy review/publish APIs remain unchanged. No arbitrary caller path is canonicalized to bypass validation.

Bound review trace: Worker.__init__ resolves project; state derives from canonical project using tasks._safe_path. review_one resolves its host-owned checkout; output derives from validated state and effect identity. ReviewRunner.review_bound uses unchanged _private_directory, which checks caller ancestry before creation. Direct BoundReviewerTests and LoadedBoundReviewerTests fixture roots already resolve their own TemporaryDirectory root. No extra production or fixture conversion is justified by this trace.

## Deterministic TDD evidence
New OwnedCaptureDirectoryTests execute real Git and real capture validation. Positive control uses a normal owned temporary directory. Alias regression creates a real private directory symlink or Windows junction (alias regression ran without skip on this Windows host), controls only the OS temp creation boundary, and executes the unchanged strict validator. Original code produces exact unsafe_capture_directory (two tests, one ERROR, actual exit1): `runtime/pr17-ci-capture-red.log`. One-line correction passes both tests, actual exit0: `runtime/pr17-ci-capture-green.log`. Same regression verifies caller-supplied aliased capture and PR review outputs still reject, with no created review output. No validator approval mocks; skip only if actual host cannot create either link type.

## Review package and limits
`runtime/pr17-ci-capture-package/fix.diff` contains only pr_evidence.py and test_pr_evidence.py changes. `freeze.json` records old committed/new raw hashes and the preserved pending Task4 docs hashes. Task4 spec/plan/proposal remain 9e533197 / 12b2c780 / fe0f3207 respectively; these are not accepted by this CI correction. No full suite, commit, push, live DB, model, native or GitHub effects performed. Portable CI remains required; actual POSIX native qualification is not claimed. Task3L and whole Issue17 remain pending.

Focused contained verification running; final result will be appended after actual process exit and receipt verification. Independent code acceptance is still required.


## Final focused receipt

93 tests in 344.838s: OK. Contained process duration345.125s; actual outer session40929 closed exit0. verified_success/source_unchanged true; exit0, cleanup_confirmed true, full stdout/stderr EOF, no truncation. No full suite rerun. Source/docs freeze hashes rechecked after completion.

```json
{
  "runtime\\verification\\pr17-ci-capture-focused\\completion.json": "46e35ddb70fef3b615d30529d4011a662e701ca2ad7349f44c1a3d8575d8da0f",
  "runtime\\verification\\pr17-ci-capture-focused\\inputs-before.json": "811442e9aa5acafed584457f72533889540e4fc45fb657557cb28fd57383195b",
  "runtime\\verification\\pr17-ci-capture-focused\\inputs-after.json": "811442e9aa5acafed584457f72533889540e4fc45fb657557cb28fd57383195b",
  "runtime\\verification\\pr17-ci-capture-focused\\stderr.log": "152fadbecf4a0749ea1f218f10c9acc779ec6104cd900cbb94ddc3462f63c743",
  "runtime\\pr17-ci-capture-red.log": "ca6636641d7a88e399b6df8c20e4362e3a94d93ba295f693657349ccdf44266c",
  "runtime\\pr17-ci-capture-green.log": "9056ab46a441e9fbbae47f9cfb1e0338d8aa111e5b26129becab7cbb28238a96",
  "runtime\\pr17-ci-capture-package\\freeze.json": "5d1441f86f881668dc733f65850cee8ec526382e22a5899fe25561bcc64e3fd1"
}
```

Suggested distinct review: inspect exact two-file diff and raw freeze, original macOS stack and RED/GREEN; verify canonicalization is exclusively owned temporary creation boundary, all capture/Source/private caller alias guards unchanged, complete full-profile/provider/proof/publication focused receipt valid, pending Task4 docs not product approval. Return exact raw-hash-bound verdict, findings, and limitations. No code/effects/test rerun necessary unless findings justify it.
