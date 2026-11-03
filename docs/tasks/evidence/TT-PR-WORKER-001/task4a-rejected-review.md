# Issue17 Task4a independent bounded implementation review

Verdict: REJECT. One important foundation defect must be fixed before this bounded stage is accepted.

Reviewer: fresh independent instance /root/pr17_task4a_independent_review, 2026-11-03. I did not implement these files. Reviewed the whole two-file change, actual private_paths/safe_config_path/full executor pins, pipeline._runtime/_current and PipelineJournal pinned existing read-only APIs. Read applicable root/checkout AGENTS and Task4 specification/plan/binding review and bounded handoff. No missing later Task4b/c functionality is being treated as a finding.

## Exact frozen identity

HEAD: 17d4a82f3b5a2a5d565e948bda0215446f41a43a

- task_tower/pr_context.py SHA256 a16935b9fe7d2f6c10d211d923613719bb180a579d4aae58b1d07cf64a49292b
- tests/test_pr_context.py SHA256 1550185933c6fad9c2fe59491063b1e13003f061c5aac09755674880602a66dc

Digests recomputed from actual files. Both are untracked; no other product changes were present. This is not PR/head/main acceptance.

## Blocking finding

[P1] Cross-check private inputs/source against executor output and instruction roots, rather than checking only the new artifact namespace (task_tower/pr_context.py lines 75-81).

The factory appends runs_dir and Superpowers root to protected, but then compares each member only with namespace. private_paths checks the private file list against each other and checkouts; neither it nor pipeline._runtime nor load_executor_config checks the source journal/PR policy/pipeline policy/connections against executor runs_dir and instruction roots. Therefore a genuine schema-valid pipeline DB inside an executor runs_dir is accepted by from_inputs and _fresh_inputs. Actual-loader contained reproduction printed source_in_runs: ACCEPTED. Moving the PR policy into the instruction root is also accepted (policy_in_pins: ACCEPTED). journal_in_runs is correctly refused because its adjacent namespace overlaps runs_dir.

This leaves the source/input protection incomplete at the foundation boundary: the executor output tree is a process-writable tree, so accepting original source journal/config there permits role output writes to overlap private host inputs. Current identity pins do not prevent in-place writes. Future per-effect freshness checks do not make original source damage safe. This contradicts the handoff's explicit claim that private files/journals/sidecars are cross-validated against executor output/instruction roots. Fix the cross-product containment/alias checks for actual private inputs and journal sidecars against all executor output/instruction roots, and add genuine negative fixtures including source-under-runs and config-under-instructions. Preserve valid sibling layouts and existing no-source-write/full-pin rules.

## Verification and evidence

Independent bounded execution used installed Python and accepted release7586df4ac2e59316521463b7526089c8314024e4 task_tower.processes.run_command, stripped token environment, scratch fixtures only, 16MiB captures. No source edits, full suite, live/private installation journal, Git mutation, native/model/network effects occurred.

- runtime/verification/pr17-task4a-independent-tests/completion.json: 9 context tests passed, unittest13.044s, runner13.265s, exit0, cleanup_confirmed true, known stream tails, no truncation.
- runtime/verification/pr17-task4a-independent-v2/completion.json and stdout.log: actual real-loader collision probe, exit0, cleanup_confirmed true, known stream tails, no truncation; source_in_runs ACCEPTED, journal_in_runs REFUSED, policy_in_pins ACCEPTED. Probe code: runtime/review-pr17-task4a-probe-v2.py. An earlier probe stopped after the expected journal refusal; its separate directory is historical, not the successful complete probe.
- Existing supplied 38-test receipt is consistent with the narrower independently rerun 9-test result; green current tests do not cover the reproduced containment gap.

The closed no-positive-authority interface, source mode=ro/initialize=False/schema validation, lifetime source identity, same-byte replacement refusal, raw/normalized provenance and Unicode PR policy fingerprint are otherwise coherent in this bounded review. A mutable schema-valid source is not accepted run authority. No current/prepared/review/effects/controller/CLI acceptance is issued. Task4b/c/full regression and later independent gates remain mandatory. Task3L is CURRENT unmet; repeat16 is not original historical provenance or legacy bridge authorization. No whole17/pilot/night readiness approval.
