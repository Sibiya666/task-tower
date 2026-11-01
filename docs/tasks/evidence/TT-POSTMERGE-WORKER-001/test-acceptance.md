# Independent TEST acceptance: TT-POSTMERGE-WORKER-001

Date: 2026-11-01. Independent acceptance agent; no source changes, commit, push, real model invocation or credential resolution performed.

## Local result

Command: `C:/Users/sibiya666/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe -m unittest discover -s tests -v`

Fresh complete run: **123 tests in 32.347s, OK (skipped=2)**, exit 0. This is 121 executed tests passing, 2 skipped, 0 failures/errors.

Platform: Windows-10-10.0.19045-SP0, AMD64; Python 3.12.14, MSC v.1944. Source checkout HEAD aab8fb56d693b5da48a4a01f01dfa499e4659bcc plus uncommitted implementation captured by hashes below. No Linux/macOS or remote three-OS CI result is claimed.

Skips: `HarnessTests.test_refuses_symlink_state_directory` (symlinks unavailable) and `JournalTests.test_rejects_symlinked_database_parent` (symlink creation unavailable). Windows junction alternatives executed successfully.

## Additional integrated acceptance probe

A separate inline probe reused WorkerTests.setUp only to create and clean a temporary real Git repository, prior accepted evidence, pinned skill and a custom Python reviewer subprocess. The source was replaced with a real GitHubSource using an independently assembled injected HTTP transport: one merged PR, matching workflow/run/attempt/head identity, three platform-specific ZIPs containing build_merge_event payloads, and correct SHA256 ZIP digests. No HTTP request left the machine and no credential helper was invoked.

Observed: 16 fixture HTTP calls across two worker instances; all windows/linux/macos passed receipts verified; custom reviewer process executed once; postmerge evidence JSON written; accepted card status done and exact merge SHA recorded. Polling a new Worker instance with the same source after completion kept the subprocess counter at exactly one. Source errors remained empty. This proves fixture receipt → three checks → separate OS process → local done, not real GitHub delivery or model behavior.

Additional independent inline probes: a no-auth GitHubSource injected transport failure left card not done and launched no reviewer; explicit needs_input result left card not done; changing the card after snapshot then calling accept_task with expected_snapshot raised `Task changed during review` and left it not done. The first snapshot probe used a Path instead of the documented card mapping and raised AttributeError; the corrected API call above passed. This was probe misuse, not an implementation failure.

## Requirement evidence from executed tests

- Missing platform waits without reviewer; failed platform produces postmerge_failed without reviewer; stale prior evidence blocks launch; reject does not close. WorkerTests covers each.
- Separate real custom subprocess returns validated request/result; mismatched ID/SHA, extra fields, malformed findings/verdict, duplicate JSON keys, unsupported config, changed skill pin, timeout and nonzero exit produce needs_input. ReviewerTests covers these; provider output is not leaked.
- Duplicate delivery/restart launches once; saved reviewed result applies after simulated interruption without another process; sticky running does not relaunch. WorkerTests covers these.
- Concurrent connections and another Python subprocess cannot reclaim running. Ordinary retry refuses running/done; recover requires literal true stopped confirmation and refuses missing/done. JournalTests covers these controls.
- Watch loop survives injected GitHubSourceError and runs a second poll before deliberate KeyboardInterrupt; WatchTests uses mocked worker/source/sleep and does not test a real outage.
- Card mutation during review and at accept_task boundary prevents done; expected_snapshot explicit probe also passed. Latest merge supersedes older failed merge for the same task.
- Expired/forged/replayed/wrong-repository/oversized/path-unsafe ZIPs, pagination limits and unknown newer run errors fail closed. Redirect strips Authorization; reviewer child omits GH_TOKEN/GITHUB_TOKEN. All are injected fixtures, not live authentication claims.

TEST verdict: accepted for the captured local Windows source. Real model/auth verification and remote three-OS CI are separate evidence obligations. No claim of remote CI completion or final task done is made here.

Final stable-source rerun independently completed with the result above. An additional latest-selection probe first persisted an old failed SHA, then polled old plus newer valid merge: the latest card reached done, reviewer subprocess count remained one, latest journal row active=true and old row active=false. Thus the historical failure was retained without becoming the active event. The final executing suite discovered 123 tests after adding the event-before-local-card regression. Real GitHub/Codex execution reported by the parent is deliberately left to its separate real-run evidence.

Final missing-card regression and independent probe passed: event receipt with absent local card leaves journal waiting, creates no replacement card and launches no reviewer; restoring the original card lets the next fresh worker poll reach done with exactly one custom subprocess. Malformed/stale existing-card blocking remains covered by the unchanged negative tests. Final fresh suite completed with 123 tests in 32.347s, OK (2 symlink skips), exit 0.

## SHA256 source snapshot

- `task_tower/__init__.py`: `c671ebd60f83582eb92badcb0aa8cbd5a259904eaee08ee9620012ee6a9f9ef0`
- `task_tower/__main__.py`: `2f706691a68a8de91870e229c607a0019880812ddede971a89580809df5e2940`
- `task_tower/bootstrap.py`: `fcb50a155850b52a8697a7f603e4af582c48bda3defd6bf87d40567f00659035`
- `task_tower/github_source.py`: `82c6b83753560e8d8aae6bc2d2ecef82297aab1e983a71a7dff37dcd383f4c85`
- `task_tower/harness.py`: `89e2792875cd2bf2d5a18e638b6894e775e1ef67b1e79ec1c6643bd762125ddb`
- `task_tower/merge_events.py`: `a442d46bc296d6a0aece334499e9785cd6ccf6ba9c27cbd2e298180e664c4269`
- `task_tower/postmerge_journal.py`: `31ee8dca1dc5da0fe43180d16d5d69725ad4a2f7d4910ff4795e37fd029c88bb`
- `task_tower/postmerge_worker.py`: `094e8fc3d8609ef271232f3d301a37071b1d693f5b145bcbdff0105bd5f3f204`
- `task_tower/processes.py`: `dadfa275cc1666f8dcb93578c38e07dd1b9543ca24d5e4c09c046a00487fdade`
- `task_tower/readiness.py`: `99b7ba8fb024a6b22bf31242c324f1fe7a77bfc31090d7facc32580538d98070`
- `task_tower/reviewer.py`: `91dfa8f4333730c30e68249385042867cda157897498add913827a49ea5a4ea2`
- `task_tower/tasks.py`: `937a76c11fab14ac5ee840feb0ba145d6497bfc576b0e8dff7ac257b074473b4`
- `task_tower/windows_job.py`: `1d478f3a7352b95d3cdc30daab5d7e0cb5a1caf0c3751488e7981a296a78deb3`
- `tests/test_bootstrap.py`: `31626a120637944567c046347020dd35bc9474460876a69aa82d313f7a68116d`
- `tests/test_cli.py`: `9834c9141d8f162b0ff0217a5a7360d149f8d05cbbd8edd8e02468f760d1ee79`
- `tests/test_github_source.py`: `37fcf1d7389416571e831056d6413080a4ad526e9289d80c1fec47f46a1d133c`
- `tests/test_harness.py`: `7cab01013bb13adf80cae1cb35895e2dceb4ad321046a81555ec4855f836bb77`
- `tests/test_merge_events.py`: `edabc2ea2542261b593cda74cbb74d340f7879c763e33ffbb8ce6105dcd291d6`
- `tests/test_postmerge_journal.py`: `d85dc44f74eb4de01fe71466d7bcec1e2ebb11c307832f8e7be837c4687612f8`
- `tests/test_postmerge_worker.py`: `1a734f84a44db18d37c7cae6112faad1d8083cf290f00f4037818bf842a1cdc7`
- `tests/test_processes.py`: `d4f239d92a3c13d765b0493bc2df33699ac24679150adbc32bf55cc3a1f5baa5`
- `tests/test_readiness.py`: `820038c6c5e927b7dbaecb68f0fc72426e88348bbc01a687ace2b128ac849eb9`
- `tests/test_reviewer.py`: `da65e15b1e5f6a619b89aab51775107e3de55710fdbc00bf5d935f74458b1b5b`
- `tests/test_task_cli.py`: `cfe0d5787b3de95e78bee8028e12f97678fc430e82fe0ad9c2964416ab18a377`
- `tests/test_tasks.py`: `8ba3a4b0f659e2dd107fd600fb627a920ba1efe6c3e0a60dfe883986d848c09a`
- `tests/test_worker_cli.py`: `dac98ab97f81e58a524e24029787f5b5c76d76ab4fa13ee5c997278d15080bf7`
