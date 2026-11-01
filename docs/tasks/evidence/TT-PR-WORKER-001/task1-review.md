# Task1 independent policy/journal review — TT-PR-WORKER-001

Reviewer: fresh independent `/root/pr_policy_review`, 2026-11-02. **Verdict: REJECT / HOLD** pending the P1 binding defect below. This is scoped Task1 implementation review, not PR acceptance, merge authorization, pilot readiness or Issue completion. No product edits, commits, pushes, live API writes or new operator assertions occurred.

## Frozen scope

Repository HEAD: `6f537c70b0c2f33e02a5385e14f5bdaf358d0059`. Four new untracked files were inspected in full; SHA256 raw bytes (the supplied UTF-8 LF canonical bindings):

| File | SHA256 |
| --- | --- |
| task_tower/pr_policy.py | 017bf9073925b8d1f47b934c444d1191aecae110bf54ea178cc93cc0e1445791 |
| task_tower/pr_journal.py | 259f46cb81330f564304ccc7d855bddfae5b85aa42f4dcd2c40f62d659262675 |
| tests/test_pr_policy.py | 5194b0f035babf6f1a21315bf1788ac36330f195fbf6024cd56cc39ee4a493f5 |
| tests/test_pr_journal.py | 14e14a6a93208113aef5c3468a520dc2eeecf67715a6dbc61a71f2372c7db7d0 |

Read repository AGENTS, accepted specification and plan, and retained R1 spec-review acceptance. Specification SHA256 a987e1df4cf20c2e6531f80f0f6852325c250638b427d86bcd97c7c347b32efa; plan SHA256 2ae227f87bd58f9f72c2d0ab2f7ead75ec8add18296e6724151f4b9b76c2fb9f. Applied independent code review and verification-before-completion skills.

## P1: publication effects accept another PR/repository's publication

`task_tower/pr_journal.py:500-504` loads a caller-selected publication ID and checks phase/owner/body hash, but does not require the publication's immutable binding, repository or PR to equal the current row. The persisted validator at lines 560-562 similarly checks effect kind and payload publication ID but not the effect binding against the publication binding. Therefore this is not merely a temporarily invalid in-memory return: the mismatched intent commits and survives a subsequent validated read.

Real SQLite hostile probe used only normal journal APIs and existing real subprocess fixtures. Starting within `JournalTests.test_postmerge_publication_individual_intents_exact_v1_body_and_full_completion`, intercepted `prepare_publication` after the original method returned owner/repo PR44's prepared publication. Under the same active owner, used `ready('other/repo',45)`, acquired that repository's exact barrier, began/confirmed its merge with exact parents, transitioned to awaiting_postmerge, began/confirmed a fresh real completed postmerge subprocess, and transitioned to awaiting_closure. Then executed:

```python
forged = journal.begin_effect('other/repo', 45, owner, 'comment_post', {
    'publication_id': publication['publication_id'],
    'body_sha256': publication['body_sha256'],
})
assert journal.effect(forged['effect_id']) == forged
print('CROSS_REPOSITORY_PUBLICATION_ACCEPTED',
      forged['binding']['repository'],
      journal.publication(publication['publication_id'])['repository'])
```

Actual output: `CROSS_REPOSITORY_PUBLICATION_ACCEPTED other/repo owner/repo`; exit 0; 1.749 seconds. Both repositories used fixture-positive completed process cleanup; no SQLite tampering, mocked database validation or live transport was used. The foreign publication was advanced to comment_intent by the other repository's intent. A later effects adapter can consequently consume a durable intent whose target PR and receipt belong to different repositories, violating exact binding and per-project authorization boundaries. A later implementation's extra checks do not repair the Task1 store invariant.

Require publication binding/repository/PR/owner equality before both comment_post and issue_close intents, and validate the reverse publication-to-effect binding relationship on every database open. Add rejected same-repository/different-PR and cross-repository probes for both effect kinds, preserving the original publication phase and effect counters after rejection. Author corrections require releasing the source freeze and fresh review of changed hashes.

## Verification and scope observations

Python: `C:/Users/sibiya666/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe`. Checks ran with routine require_escalated authorization because the default sandbox is unreliable for these checks.

- `python -m unittest tests.test_pr_policy tests.test_pr_journal -v`: exit 0, 24 tests, 9.419 seconds, OK. Includes actual SQLite/process lock, process-death lock release, unknown intent, durable owner loss, cleanup-proven revisions and individual comment/closure substates.
- `Get-FileHash` over all four frozen files: exactly the bindings above.
- Additional real SQLite cross-repository probe above: exit 0 and undesired acceptance reproduced.
- Fresh complete suite launched with `python -m unittest discover -s tests -v`; final result recorded below when complete. Earlier author full-suite evidence is not reused as final proof.

The strict duplicate/unknown-key policy, type/bound checks, private alias/sidecar defenses, retained operator assertion, durable PID/owner/OS lock, revision deadlines/counters, old receipt and reviewer-instance fencing, unresolved-intent fencing, append-only historical bindings, and saved full publication-proof barrier were inspected. No additional blocking finding is asserted from those checks. Zero prior launches correctly permits clean prelaunch revision; completed/failed role paths require cleanup evidence. Separate read-only effect accessors are acceptable factoring. No global exclusive-writer authorization is inferred: actual runtime readiness remains externally blocked until genuine authorization/setup. Provenance-bound recovery transfer, genuine external verified_done, source/reviewer/controller/pilot implementation remain later tasks, not demanded as Task1 features. The existing prohibition on a different PR acquiring a live barrier is intentional.

Complete-suite disposition: At the coordinator's explicit request, stopped only this review's owned exec session `17698` using `write_stdin` Ctrl-C. Tool returned completed exit code 1. This broad run was interrupted and is **not final verification evidence**; no complete-suite success is claimed. The scoped 24-test completed run and actual P1 probe above remain the evidence for this rejection. Source freeze may now be released by the coordinator for the bounded correction; this verdict remains bound only to the four frozen hashes above.

## R1 independent re-review — 2026-11-02

**Current verdict: ACCEPT Task1 policy/journal implementation at the exact R1 bindings below.** The original P1 rejection and interrupted full-suite history above are retained. This acceptance is scoped to Task1; it is not whole-branch PR acceptance, installed readiness, external writer authorization, final integration verification or Issue17 completion.

Repository HEAD remains `6f537c70b0c2f33e02a5385e14f5bdaf358d0059`; four new files remain the scope:

| File | R1 raw SHA256 |
| --- | --- |
| task_tower/pr_policy.py | 017bf9073925b8d1f47b934c444d1191aecae110bf54ea178cc93cc0e1445791 |
| task_tower/pr_journal.py | bddab27d97d7e6bcbf914baa9e84aece5b8de68a1112ac525bcdffa5c1d65431 |
| tests/test_pr_policy.py | 5194b0f035babf6f1a21315bf1788ac36330f195fbf6024cd56cc39ee4a493f5 |
| tests/test_pr_journal.py | ecae5d56a1de936b281ae8b5cf8ab0cc49aa13074df07c9ad24cac9032fbcb04 |

`Get-FileHash` independently confirmed these supplied UTF-8 LF bindings. Policy and policy tests are unchanged. Inspected the complete correction: `_publication_binding` enforces all nine binding fields, repository/PR key consistency and owner; `begin_effect` applies it before either comment or close intent; `prepare_publication` checks it before returning an existing receipt; `_validate_publication` and the reverse effects pass enforce matching publication/effect identity and reciprocal effect IDs. Stored comment body hashes, close Issue IDs, PID ownership and publication phase references are checked. Historical role effects still validate against their archived revisions; a stale revision cannot become a current publication effect.

Independent checks, same absolute Python as above and routine require_escalated:

- `python -m unittest tests.test_pr_policy tests.test_pr_journal -v`: exit 0; **28 tests in 14.093 seconds, OK**. Read all new negative tests, including public foreign comment/close rejection with unchanged database bytes, existing-receipt return rejection, cross-repository corrupted reciprocal references, stale-revision effect binding, and same-repository different-PR intent with an actual target barrier. The latter deliberately combines independently valid real-process host snapshots so the exact PR guard is tested rather than merely failing the normal single-repository barrier. Positive own comment, exact full completion and unchanged legacy raw receipt publication identity pass.
- Additional independent public-API probe rebuilt two repositories through actual completed subprocesses and journal states (`publication_ready`), then attempted owner/repo PR44's publication under other/repo PR45 for both comment_post and issue_close. Each attempt raised `Publication revision/owner mismatch`, left database bytes and original publication unchanged; the own-target comment intent subsequently succeeded and survived `effect()` validation. Actual output: `FOREIGN_REJECTED comment_post Publication revision/owner mismatch`; `FOREIGN_REJECTED issue_close Publication revision/owner mismatch`; `OWN_PUBLICATION_ACCEPTED`. Exit 0, 1.701 seconds.

The original reproduced P1 is resolved at both prewrite and persisted-read boundaries; no remaining blocking finding identified in this scoped review. No new broad legacy suite run was performed or claimed. No product edits, commits, pushes or live API writes occurred. Later tasks still own external observations/verified_done, controller recovery transfer, complete integrated branch verification and the genuine runtime pilot. Actual global writer exclusivity remains an external readiness prerequisite, never inferred from this acceptance.
