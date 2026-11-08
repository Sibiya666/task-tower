# Fresh Git identity query implementation plan

> **For agentic workers:** Use superpowers:executing-plans for this one bounded task, then independent whole-diff review.

**Goal:** Reduce fresh identity-query subprocess overhead while preserving every validation boundary.
**Architecture:** Combine adjacent root/Git-dir reads only; retain fresh HEAD and subsequent checks at their existing positions. Known LF paths keep the separate-query route.
**Tech Stack:** Python 3.11+, standard library, existing Git and unittest.
**Spec:** [Approved design](../specs/2026-11-08-ci-git-identity-design.md).

## Global constraints

Keep all security predicates, deadlines/assertions, full discovered suite, fixtures,
skips, workflows and PR/main gates. No caching, configuration changes, installation,
platform change, private database migration or old worker activation.

## Review focus

- Literal LF framing must reject missing/extra/empty records without treating Unicode separators as delimiters.
- Unbound/wrong linked Git directories and nested roots must remain rejected.
- HEAD mutation during filesystem validation must be caught by the later read.
- Unborn/detached HEAD handling must remain policy-dependent.
- LF in a root or bound Git directory retains the original query route.

## Task 1: Implement and verify fresh identity batching

Files: modify `task_tower/pipeline_inputs.py`; create
`tests/test_pipeline_identity.py`; retain existing input/publication regressions.
Interface: `_repository(root, policy)` continues returning the validated Path.

- [x] Write focused real-Git tests for ordinary and linked repositories, nested/wrong identity, Unicode/spaces, malformed byte framing, detached/unborn policy and HEAD mutation during filesystem validation. Add meaningful process-count regression: one fresh path query per validation, and a second call sees changed identity. POSIX LF fixture covers root and bound Git directory.
- [x] Run `python -m unittest tests.test_pipeline_identity -v`; observe optimization/framing regressions fail on original code, with existing behavior cases passing.
- [x] Implement only the combined path query and strict parser, with known-LF fallback. Keep HEAD, branch/ref and filesystem checks at their original boundaries.
- [x] Run focused tests and `python -m unittest tests.test_pipeline_inputs tests.test_ci_unittest -v`; require success.
- [x] Measure unchanged existing publication workload with the original and changed `_repository`, alternating three pairs, token-stripped environment; retain timings and process counts privately. Do not add a permanent benchmark job.
- [ ] Run `python -m unittest discover -s tests -v` on frozen source, record complete output and source identity; require success before delivery.
- [ ] Commit source/tests/evidence summary, obtain independent whole-diff approval at actual fresh H/B, push/open PR and publish genuine acceptance only from that verdict.
- [ ] Require all real PR CI, protection, mergeability/resolved conversations, manager merge serialization and protected expected-head merge. Fresh fetch <=60s/local Git <=10s.
- [ ] Verify full exact-main CI artifacts/inventory/event and independent postmerge acceptance before canonical child close/history/readback. Keep parent epic open and preserve other owners/risks.

Execution authorized directly by user: implement approved design and deliver to main
with all checks; address manager for merge coordination. No extra per-step approval.
