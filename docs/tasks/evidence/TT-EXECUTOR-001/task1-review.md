# Task 1 independent review — TT-EXECUTOR-001 / Issue #15

Verdict: **REJECTED** for the four-file historical Task 1 stage below. This is not whole-Issue or PR acceptance. Reviewer is a distinct instance from the implementer; no production files, commits or remotes changed.

Reviewed accepted executor design/plan, repository/workspace AGENTS and parallel development policy. Dispatcher delta is confined to resolving the existing host token and passing it to GitHubSource; no authorization grants or verified_done weakening appear in this delta.

## Blocking finding

P1 — `load_executor_config` permits Codex argument templates that bypass the saved safety/model policy. Its exact-token denylist does not establish the specified safe Codex invocation. Independent executable-only temporary fixture counterexamples all loaded successfully with kind=codex:

- `--sandbox danger-full-access`
- `--approve-for-me` while normalized `approve_for_me` is false
- `-mchosen`
- `-c model="chosen"`
- `--dangerously-bypass-approvals-and-sandbox=true`

Model selection and sandbox/hook/rule bypass are explicitly excluded; approve-for-me requires its saved policy switch. Restrict Codex profile argv to the executable only and construct the accepted arguments in the harness, or enforce an equivalent closed safe grammar. Add regressions before rereview. Explicitly trusted custom processes retain their stated arbitrary-process trust boundary.

## Verification and remaining scope

Independent focused run: actual bundled Python, `-m unittest tests.test_dispatcher tests.test_executor_profiles -v`: 27 tests, PASS, one Windows symlink-privilege skip. Independent in-memory counterexample checks above reproduced the blocker. The reported implementation RED/full-suite results were not independently rerun in this review and are not asserted as reviewer evidence.

Current code establishes canonical policy fingerprinting, exact allowlist row keys/bindings, max_active default two and upper bound two, private checkout exclusions, ancestor reparse/symlink rejection and file hardlink rejection; case-insensitive child token stripping leaves the input mapping unchanged. Task 4 must actually use this environment for both probes and execution and revalidate authority/instruction files immediately before launch; this helper alone proves neither.

Superpowers checks validate actual manifest file content using canonical UTF-8/LF and its digest. `revision` currently has SHA syntax validation only: it is an installation-declared provenance label, not cryptographic proof of the installed cache's Git origin. The real installed plugin root is not a Git checkout. Do not claim its declared revision verified without independently matching approved manifest bytes. Missing/drifted manifest files fail on reload; late launch drift detection remains Task 4 scope.

## Canonical source manifest

SHA-256 over UTF-8 text normalized to LF; evidence excluded to avoid self-reference. These hashes identify this rejected stage snapshot, not any later full-Issue diff.

| File | Canonical SHA-256 |
| --- | --- |
| `task_tower/executor_profiles.py` | `2fca9e433f7c8eb3018fa6ba7e50197b6b3e648669c164ec42a2afdae4d04d36` |
| `tests/test_executor_profiles.py` | `f53627708968d3ec970bb73ddcfdb004c254b0d3602d62f0e888a7217624ffb8` |
| `task_tower/dispatcher.py` | `b070801cf3085362b730b0adc8028ea91b2d56951be9398037ba3e017d9790e4` |
| `tests/test_dispatcher.py` | `041a03f10bd61f5a0a1204875f08c890ef83d2041cfd1261ec82efe562808c6d` |

## Current rereview supplement - ACCEPTED

The initial rejection above is preserved as historical evidence. Current Task 1 verdict: **ACCEPTED**, bound exclusively to the four canonical file hashes below. This does not grant whole-Issue, PR, execution or postmerge acceptance.

Independently reread the actual repaired files and auth-only dispatcher delta. Codex profile argv now contains exactly one absolute executable; the future harness must build the fixed safe invocation and apply the saved approve_for_me switch. Arbitrary trusted custom argv remains explicitly installation-owned arbitrary-process authority, without claims of Codex safety or model policy enforcement. The P1 finding is resolved.

Independent focused verification using actual bundled Python: `-m unittest tests.test_dispatcher tests.test_executor_profiles -v`, 30 tests PASS in 1.289 seconds, one Windows symlink-privilege skip. Independent temporary fixture counterexamples reran all six unsafe Codex suffixes (including short sandbox flag) and each was rejected with ValueError. New strict policy type tests and trusted-custom boundary test also pass. No remaining blocking finding within Task 1 scope.

All provenance and later-stage limitations recorded above still apply: source revision is declared provenance, actual manifest bytes are checked, and Task 4 must revalidate late drift and use child_environment for probes and launches. No cryptographically verified installed Git revision or real execution capability is asserted.

| File | Current canonical SHA-256 |
| --- | --- |
| `task_tower/executor_profiles.py` | `b80944cceefcb359f4be6597b1780227cb7525da08e2d8c626f6b9b8f4a5d901` |
| `tests/test_executor_profiles.py` | `26aae2458732e868ffa4290c8d47ef9dec4b3f9389412a58c3bd1131f2ccc8ec` |
| `task_tower/dispatcher.py` | `b070801cf3085362b730b0adc8028ea91b2d56951be9398037ba3e017d9790e4` |
| `tests/test_dispatcher.py` | `041a03f10bd61f5a0a1204875f08c890ef83d2041cfd1261ec82efe562808c6d` |
