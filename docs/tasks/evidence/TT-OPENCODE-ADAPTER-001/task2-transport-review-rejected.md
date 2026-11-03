# Independent Issue21 Task2 transport review

Reviewer: /root/opencode_task1_acceptor. Verdict: **BLOCKED / changes required** for the frozen candidate below. No source changes, native OpenCode/probe/provider/auth activity, full-suite run, Git mutation or remote effect performed.

Base HEAD64b9702f6ddadad89c76bfba5bed2ff75d87fb05 verified. Read approved design/plan Task2, concrete brief, frozen handoff, complete three-file candidate and actual tracked diff. tests/test_executor_processes.py is unchanged. Verified handoff SHA256 a610e5953b21da45c8047ab285017075db82c65afc714fc227ffe1bb894782e5, freeze SHA256 c35518813d4d8fc5754a95813f3fa9733e186ad4e69e5643c3f2ccd95f0ab3ef, package SHA256 a3f0a24e8d455d72d5b14386280ce8643277912579ea92ff4de6126c3fba5116 and all three actual file hashes unchanged after review.

## Blocking finding P2: storage-construction cleanup stops at first close error

In processes._stdin_storage Windows exception handler (lines231-239), cleanup closes writer then reader without protecting individual closes. If setup fails after both streams exist (e.g. os.set_inheritable fails), and writer.close raises, reader.close and remaining raw-handle cleanup are skipped. The tuple was never returned to _stage_stdin, so its finally block cannot recover ownership. This leaks a real read-only staging handle, keeps its delete-on-last-close temporary file alive, and _stage_stdin/run_command subsequently map OSError to stdin_binding_mismatch with cleanup_confirmed=true despite lost staging cleanup. The POSIX constructor cleanup loop has the same short-circuit structure for errors on cleanup; repair both platform ownership paths rather than only the later _stage_stdin cleanup already tested.

Independent deterministic Windows probe on actual bundled Python monkeypatched only fdopen wrappers and set_inheritable: after both real storage streams were created, force set_inheritable to raise OSError; wrap writer.close to close its underlying genuine stream then raise OSError. Actual result: `failure writer close confirmation failed`, `created 2 closed [True, False]`. Reviewer explicitly closed the leaked reader afterward. No child was created. This is distinct from existing test_staging_writer_close_failure_also_closes_reader, which injects a returned storage tuple; that test never exercises a constructor failure before tuple ownership transfer.

Required change: cleanup every owned stream/raw handle independently even if an earlier cleanup fails; retain bounded failure and do not claim cleanup confirmed where ownership remains uncertain. Add a deterministic constructor-failure/close-failure regression that asserts both underlying streams and any retained raw handles are closed; exercise both ownership-transfer seams. This is a real acceptance requirement under Task2 all-failure handle cleanup, not a demand for unrelated full-suite repetition.

Probe outline:

```python
opened=[]; original=os.fdopen
class BrokenWriter:
    def __init__(self, stream): self.stream=stream
    def fileno(self): return self.stream.fileno()
    def close(self):
        self.stream.close()
        raise OSError('writer close confirmation failed')
def wrapped(fd, mode, **kwargs):
    stream=original(fd, mode, **kwargs); opened.append(stream)
    return BrokenWriter(stream) if mode=='w+b' else stream
with patch.object(processes.os,'fdopen',side_effect=wrapped), patch.object(
        processes.os,'set_inheritable',side_effect=OSError('inheritance failure')):
    try: processes._stdin_storage()
    except OSError: pass
print([stream.closed for stream in opened]) # actual [True, False]
# Reviewer cleanup closed every remaining stream.
```

## Other review observations and limits

Strict optional four-key binding, <=4194304-byte cap, single-link regular identity and nofollow source read, bounded expected+1 hashing/copy, before/open/after/path checks, source closure before spawn and read-only anonymous child transport are materially implemented. None preserves the legacy delegate/DEVNULL path; WindowsJobProcess preserves suspended Job assignment before resume and caller stdin ownership. Parent read copy closes after successful construction. Existing deterministic mutation/short-write/stream-conversion/poststage replacement and early-exit/nonreader timeout/cancel descendant tests provide useful coverage.

The reported29-test focused pass/1 existing skip and real60 362380-byte digest transport are implementer evidence, not independently rerun or treated as native qualification. I did not repeat the identical suite because the independent failure probe resolves a previously untested obligation. No other confirmed blocker identified; approval remains withheld until the concrete cleanup flaw and regression are reviewed on a new freeze. Root may run its owned full suite after code approval; this report imposes no undefined full-suite precondition. This review does not qualify installed OpenCode, native platform behavior beyond controlled transport fixtures, later Tasks3-5, PR/main or the whole Issue.

## Exact frozen files

| File | Raw SHA256 |
| --- | --- |
| task_tower/processes.py | 877a44d9aae2ffc13604f20e04206fd4d4ea710f43debc5ee16693b3afebdd44 |
| task_tower/windows_job.py | fa1982c1032e20e57dcee00c27fc07bba11ef7d77000c530f46be80d13f9ad09 |
| tests/test_opencode_transport.py | 8125b6bb66a8f09d536b214e57baab16a12db7fa9a51e09885a3fd34729777f3 |
