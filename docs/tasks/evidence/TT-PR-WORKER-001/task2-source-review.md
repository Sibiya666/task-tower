# Task2 independent source review — TT-PR-WORKER-001

Reviewer: `/root/pr_source_review`, 2026-11-02. **Verdict: REJECT / HOLD** for the P1 final mergeability drift below. Scoped source acceptance only; this is not whole-PR acceptance, stage-authority authentication, writer authorization, installed pilot readiness or Issue completion. No product changes, commits, pushes or live API writes occurred.

## Frozen bindings

HEAD: `f29a4e7b41ac7fbb92b276fcd49a4c6f58492273`. Independently read repository AGENTS, accepted specification/implementation plan, retained Task1 R1 acceptance and implementation ledger. Applied independent code review and verification-before-completion instructions. Peer `pr_review.py` was inspected for request/profile/pin compatibility; its model runner and shared PID implementation have a separate independent reviewer.

| File | Raw SHA256 | UTF-8 LF SHA256 |
| --- | --- | --- |
| task_tower/pr_source.py | c6f91e5ba9e5a6fbc5a2fd4d7339d5acf5e3fe209e5ed024b8e412de397bc427 | c6f91e5ba9e5a6fbc5a2fd4d7339d5acf5e3fe209e5ed024b8e412de397bc427 |
| tests/test_pr_source.py | 10a5cefb9a878a46c1838a898a3f5b423fe33dd17ccaba907aa5b68d35eb79ed | 10a5cefb9a878a46c1838a898a3f5b423fe33dd17ccaba907aa5b68d35eb79ed |
| tests/fixtures/pr_source_github_2026.json | 5926d90ab449ab421259e3ac4349f472bb1a25623c648a49b71ed08536bbbfea | bf53dd5150490c879097659554eebc4dbe856d7c04761007a98a5f181b9af71a |

UTF-8 LF means decode UTF-8 with optional BOM removal and normalize CRLF to LF, without JSON reserialization. Raw fixture bytes must retain their distinct binding. Runtime JSON fingerprints use the actual `pr_policy.canonical` algorithm instead; these schemes are not interchangeable.

## P1: final observed blocked mergeability still returns ready

`PRSource.snapshot` initially rejects unknown/false mergeability or a non-clean mergeable state. Its final PR reread compares only head, base, body, state, draft, commits and changed_files. It omits `mergeable`, `mergeable_state` and `merged`. Consequently a final server observation explicitly reporting `mergeable=False, mergeable_state='blocked'` does not invalidate the initial ready observation. The returned source bundle still contains the initial clean PR and reports ready. This violates the required fail-closed current mergeability/source consistency gate. A later controller reread through this same API does not repair this collection-window error.

Independent hostile probe ran the existing positive whole-snapshot test through its real HTTP-transport boundary, retaining all production snapshot parsing, CI/platform/protection/thread/Issue logic. Wrapped `_get` only to return a copied PR with `mergeable=False, mergeable_state='blocked'` on every second `/pulls/1` read; wrapped `snapshot` only to capture its returned results. The test's existing positive assertion still passed. Independently asserted both the final blocked server observation and the first snapshot's ready=True. Actual output:

```text
FINAL_PR_BLOCKED_BUT_SNAPSHOT_READY True blocked
```

Exit 0, 0.431 seconds. No snapshot gate was replaced, no live transport was used and no product file was edited. Require final PR mergeability/merged observations to be consistent and ready (unknown is blocking), with regression cases for clean-to-false, clean-to-unknown and clean-to-blocked transitions. Author correction needs coordinator release of the freeze and new exact-hash review.

## Independent verification and inspected boundaries

`C:/Users/sibiya666/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe -m unittest tests.test_pr_source tests.test_pr_review -v`: exit 0; **32 tests in 6.957 seconds, OK**. These are independently executed results, not reused author claims. Includes real temporary Git/bare-object transfer, complete binary diff/rename manifest, source-to-role request binding, strict profile drift rejection, actual role subprocess, timeout/descendant cleanup and hostile output checks. Scoped tests do not establish a real hosted pilot or complete-suite success. Routine reads/tests used require_escalated because of the known default sandbox failure.

Inspected GET-only REST collection and fixed read-only GraphQL query, redirect rejection, response/page limits, changing totals/duplicate identities, Issue title/body digest inclusion and reread, exact remote identity, fresh template-free Git repository, disabled hooks/global configuration/replacements/external diff/textconv, complete binary/raw manifest and bounded blobs, rename byte-path preservation, submodule refusal and private path checks. Producer recomputes actual pins and whole-profile fingerprints from host-injected `_review_profile`; installed policy exact task keys do not accept that injection. Genuine installation-owned authority remains Task3 responsibility; a correctly hashed arbitrary authority object is not authenticated stage authority.

CI inspection covered latest IDs per app/context, ambiguous publisher refusal, failed/skipped/neutral checks, separate own-acceptance status handling, and no own acceptance contribution to nonacceptance input digest. Platform proof uses current Actions check/suite, same-repository PR/head/base run, latest-attempt jobs linked by exact check_run_url, and reserved hosted group/official single label rather than raw job-name inference. Fixture provenance honestly says synthetic and distinguishes coordinator-observed field shapes from a raw response archive. Unknown/self-hosted/custom/unlinked/stale cases block. This reviewer did not perform a live GitHub observation or independently authenticate the coordinator's live observation.

Inspected effective rules/ruleset bypass rejection, administrator enforcement, actor equality, merge-method/queue restrictions, server-required app bindings, unresolved human threads and changes-requested handling. No additional blocking finding is asserted in this scoped report. Existing positive tests do not cover the demonstrated final mergeability drift. Source remains frozen pending coordinator decision; no readiness or merge authorization follows from the passing tests.

## R1 independent source re-review — 2026-11-02

**Current verdict: ACCEPT Task2 source implementation at the exact R1 bindings below.** The rejected original review and reproduction remain above. This is scoped source implementation acceptance; unfinished Task3 authority loading, external writer authorization, installed pilot, controller/effects and final PR acceptance remain separate gates.

HEAD: `59b0a49644fbe8a0bfc691c83d75e2d894d4fa04`. Source files remain uncommitted. Independently recomputed raw and UTF-8 LF hashes:

| File | Raw SHA256 | UTF-8 LF SHA256 |
| --- | --- | --- |
| task_tower/pr_source.py | d8225dc9a6e786358078565a86b822c547a403cc57505b9120fac6d6569b1cbb | d8225dc9a6e786358078565a86b822c547a403cc57505b9120fac6d6569b1cbb |
| tests/test_pr_source.py | 6e9d8df9a1d92cd37fce7168c89891dc9e2617767d485a2e10b796683c17926e | 6e9d8df9a1d92cd37fce7168c89891dc9e2617767d485a2e10b796683c17926e |
| tests/fixtures/pr_source_github_2026.json | 5926d90ab449ab421259e3ac4349f472bb1a25623c648a49b71ed08536bbbfea | bf53dd5150490c879097659554eebc4dbe856d7c04761007a98a5f181b9af71a |

The final PR typed canonical projection now compares number, head, base, body, state, draft, merged, mergeable, mergeable_state, commits and changed_files. JSON canonical comparison distinguishes true from 1. Final collection also rereads reviews, resolved-thread/review-decision state, effective protection and complete current head CI lists, including Actions latest-attempt/platform proofs. Own acceptance observations refresh separately and remain outside the nonacceptance digest. This resolves the original P1 and avoids discovering reruns solely by rereading old check-run IDs.

Fresh independent verification with the same absolute Python and routine require_escalated:

- `python -m unittest tests.test_pr_source tests.test_pr_review -v`: exit 0; **35 tests in 7.469 seconds, OK**. Source regressions cover typed final PR drift, unknown/blocked mergeability, new queued check rerun, current status, human review/thread/decision, protection and latest Actions attempt drift. Source-to-role real Git/binary/rename/process seam remains passing. This run is not a broad legacy suite or hosted pilot.
- Additional independent lower-HTTP-transport probes used `SourceTests.whole_source` with response-copy mutations only, retaining production source gates. Reproved the original final clean-to-false/blocked transition; separately changed second Issue body, second main SHA, second aggregate checks list by adding a new queued run, second reviews list by adding CHANGES_REQUESTED, and second Actions run observation to queued attempt3. All six raised `PRSourceError('source_incomplete')`; no returned ready bundle. Actual output: `REJECTED original-mergeability source_incomplete`, `REJECTED issue-body source_incomplete`, `REJECTED main source_incomplete`, `REJECTED new-rerun source_incomplete`, `REJECTED review source_incomplete`, `REJECTED attempt source_incomplete`. Exit 0, 0.403 seconds.
- The same probe counted **40 requests** for a stable positive three-platform fixture, including exactly two PR, two Issue and two GraphQL observations. Pagination/request-byte/time limits remain applied to every read; the additional pass is finite, with no retry-until-stable loop. Required-check and supplying-ruleset collection multiply the finite page budget. This is bounded collection, not an atomic GitHub transaction or a new wall-clock guarantee.

API payload shapes and endpoint routes are unchanged by this correction: the existing current-run/check/suite/job fixtures and transport tests exercise the same premerge REST/GraphQL schema. No new live API observation is claimed. GitHub offers no atomic multi-endpoint snapshot; sequential double collection detects observed inconsistency, while later effect gates still must freshly recheck before each authorized write. No absolute guarantee against changes after the final observation is inferred.

No remaining blocking finding identified in this scoped source review. Reviewer/PID acceptance is separate; it is not replaced by this verdict. No product edits, commits, pushes, live API writes or invented authority occurred. The original freeze may be released by the coordinator after recording this exact-hash verdict.
