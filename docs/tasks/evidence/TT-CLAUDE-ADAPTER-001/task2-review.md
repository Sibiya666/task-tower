# Task 2 independent review — REJECT

Date: 2026-11-02. Reviewer: distinct `claude_stream_acceptance` agent; no implementation edits. Scope: Task 2 incremental parser and optional shared-runner observer only. HEAD: `91ed6500140f1a8221e1b5c52fea2ae6cc786605`. This verdict binds the working-tree files below, not a PR or Issue acceptance.

Reviewed complete actual four-file diff, complete parser/process code, result validator, legacy callers (worker/reviewer/delivery/CLI), accepted design and Task 2 plan. Specification canonical SHA-256 `8d1c587b62cff7ded7906a450800d722f50bf285d835e9c0ed1e794a6080c3bd`; plan `30f8ff37c16b0ae2372151abb7ef27f87be7ad98f5b0dd2b415fb6efb230cb1f`.

## Blocking finding

**[P1] Cancellation and timeout precedence is bypassed by observer failure.** `task_tower/processes.py:215` tests `drains[0].observer_failed` before polling durable cancellation or elapsed timeout. When malformed stdout and cancellation arrive during the same wait interval, the next iteration returns `failed` without consulting the now-true cancellation predicate. An exception from that predicate can similarly be hidden instead of preserving `unknown`. The accepted design expressly requires timeout/cancel/uncertain cleanup precedence. This matters to worker outcome mapping and cancellation evidence, even though process containment still succeeds.

Independent native Windows reproduction, bundled Python, no Claude/model invocation:

```python
import threading, sys
from task_tower.processes import run_command
cancel = threading.Event()
def observer(chunk):
    cancel.set()
    raise ValueError('neutral')
result = run_command(
    [sys.executable, '-c', "import os,time;os.write(1,b'x');time.sleep(10)"],
    '.', 3, cancel_requested=cancel.is_set, stdout_observer=observer)
assert result['status'] == 'cancelled'  # ACTUAL: failed
```

Observed: `status=failed`, `stdout_observer_failed=true`, `cleanup_confirmed=true`, `stdout_tail_unknown=false`, duration 0.265 seconds. Evaluate cancellation/predicate uncertainty and timeout before selecting neutral observer failure; retain ordinary contained cleanup and draining. Add meaningful regression coverage for concurrent cancellation, predicate exception and elapsed timeout alongside observer failure. Fresh source binding and independent review are required after correction.

## Verification and strengths

Independent command `python -m unittest tests.test_claude_adapter tests.test_executor_processes tests.test_processes -q`: 47 tests, 6.776 seconds, OK, one existing symlink privilege skip. Additional independent randomized byte partitions of CRLF/no-final-newline/multibyte UTF-8: 200 cases passed. Five malformed-prefix cases (invalid UTF-8, overflow float, lone surrogate, duplicate key, excess nesting) remained irreversibly invalid after valid-looking final data and cleared pending storage.

Parser retains bounded incomplete line and nested result, discards content after invalidity, strictly validates duplicate keys/UTF-8/nonfinite values/depth/exact nested binding, and does not accept unknown terminal subtypes or post-result events. Observer sees bytes beyond stored prefixes and catches BaseException without leaking exception details; final EOF race cannot resurrect a passing result. Legacy no-option calls select the unchanged legacy function and preserve result shape. No second runner or unmerged Issue16 dependency was introduced.

Full-suite outcome was not independently observed for this freeze; the supplied private ` .task-tower-task2-logs/full-final.log` path did not exist when checked. This rejection does not depend on full-suite outcome. No claim of Task 3 common-worker integration, installed Claude pilot, cross-platform acceptance or whole Issue20 acceptance.

## Frozen manifest

SHA-256 columns are raw bytes and UTF-8 text normalized CRLF→LF respectively.

| File | Raw | Canonical |
|---|---|---|
| task_tower/processes.py | 4809b98c8ebea0eee437e606b0dc8a9bbc120c03310a3c0e024dcb48572d4159 | 3ab008ccff29490f8900aa764d42cdf8aa007589f23094bc1ec57516e89ec79d |
| task_tower/claude_adapter.py | 5aab48674db0d42ebfb6a82e4af9b8947c0863940edc8567fc3a3ed0ec26df79 | 5aab48674db0d42ebfb6a82e4af9b8947c0863940edc8567fc3a3ed0ec26df79 |
| tests/test_executor_processes.py | f878c248137dc8d26f0656dcf7491f65406ea18910afe01cdc0e2c7eba0774d1 | f3a65affa06660ff061d2a7af76cbb2e29ba6d6d30278c794aa820080e35ee78 |
| tests/test_claude_adapter.py | 126b2ecb4406325f5a751b5d07cb6ebd37202fc9cfd4031b784b365860f664ab | 126b2ecb4406325f5a751b5d07cb6ebd37202fc9cfd4031b784b365860f664ab |
| tests/test_processes.py (unchanged) | 6bd2c7329148f24cfc3128ae91fac427767d1587b5ce20eb24670f8f6a5ba24f | 59a3715597fd3ff33e3c19bbd8ac0c2a80eba38a072d5cdc9f53d5bda802f9b6 |


---

# R1 Task 2 independent re-review — ACCEPT

Date: 2026-11-02. Same independent reviewer, distinct from implementer. The original REJECT above is preserved byte-for-byte as a prefix (original SHA-256 `1e26a9cc43adf5d605b2e0f72323aadb35790b5a21cea685802c65a5ea304fb7`). This R1 verdict supersedes that finding for the newly frozen files only. HEAD, specification and plan bindings remain as above; no implementation source edits were made by reviewer.

Reviewed the whole actual four-file diff again, with focused inspection of revised polling and final-drain reconciliation. Durable cancellation/predicate uncertainty and the active wait deadline now precede observer failure. Late observer failure resamples durable cancellation and predicate uncertainty, preserves stronger cleanup/unknown/cancel/timeout outcomes, and cannot allow success. Drain join latency after proved child exit does not invent a new execution timeout. **No unresolved blocking findings in Task 2 scope.**

Independent actual native Windows bundled-Python probes, all passed:

| Probe | Actual status | Exit code | Cleanup confirmed / stdout EOF |
|---|---|---|---|
| Original observer sets cancel then raises SystemExit | cancelled | 1 | true / true |
| Observer failure plus cancellation predicate exception | unknown | 1 | true / true |
| Active execution deadline plus observer failure | timeout | 1 | true / true |
| Fast exit, observer delayed 0.35s beyond 0.2s execution timeout | failed | 0 | true / true |
| Cancellation arrives during late observer/drain join | cancelled | 0 | true / true |
| Predicate uncertainty arrives during late observer/drain join | unknown | 0 | true / true |
| Concurrent active cancellation and expired deadline | cancelled | 1 | true / true |
| Observer failure plus injected Windows Job close error | cleanup_failed | 1 | false / true |

Fresh independent focused command `python -m unittest tests.test_claude_adapter tests.test_executor_processes tests.test_processes -q`: **52 tests in 8.158 seconds, OK (one existing symlink privilege skip)**. The unchanged parser retains the original review's 200 independent partition and five irreversible malformed-prefix checks; these were not redundantly rerun. Original source/caller/result-schema inspection remains applicable. Read the actual completed author full-suite private log at workspace `.task-tower-task2-logs/r1-full.log`: **491 tests in 111.977 seconds, OK (four skips)**. Full-suite log SHA-256: `cd286e2a9b22c71f1f0a12d88da4264a77ae9fd4be940500ef71df06daff9639`. The full suite is author execution evidence inspected by this reviewer, not a separate reviewer rerun.

R1 raw/canonical SHA-256 manifest (independently recalculated):

| File | Raw | Canonical |
|---|---|---|
| task_tower/processes.py | 854c662b731841df5197ddc2c820ddb15720e2aea0aa5d322e668d62c764cd94 | 80e3fdb21beedcd9c423e6c0eb4b0242aa2a6114418c0b5565d0e84f9c3f368a |
| task_tower/claude_adapter.py | 5aab48674db0d42ebfb6a82e4af9b8947c0863940edc8567fc3a3ed0ec26df79 | 5aab48674db0d42ebfb6a82e4af9b8947c0863940edc8567fc3a3ed0ec26df79 |
| tests/test_executor_processes.py | e2887b1624dbb47c5bfaed4e939dcb55bdb06c4e3acd1bf2d429235ddb537981 | b6e3569dd1c34ae3b5c7991c58b4f0b884c65fb5a78b4f236f568dea5596b6bf |
| tests/test_claude_adapter.py | 126b2ecb4406325f5a751b5d07cb6ebd37202fc9cfd4031b784b365860f664ab | 126b2ecb4406325f5a751b5d07cb6ebd37202fc9cfd4031b784b365860f664ab |
| tests/test_processes.py (unchanged) | 6bd2c7329148f24cfc3128ae91fac427767d1587b5ce20eb24670f8f6a5ba24f | 59a3715597fd3ff33e3c19bbd8ac0c2a80eba38a072d5cdc9f53d5bda802f9b6 |

ACCEPT is limited to plan Task 2 code and tests under this manifest. It establishes neither Task 3 worker integration, installed Claude behavior/pilot, cross-platform acceptance, whole Issue20 development/test acceptance, PR head/base acceptance nor merge/main acceptance. Any source change invalidates this binding.
