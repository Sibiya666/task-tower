# Task 5 independent publication review

Verdict: **ACCEPT for the five-file Task 5 publication boundary; no blocking findings.** Reviewer /root/pipeline_publish_review is distinct from the implementer. No product edits, commits, pushes or live network writes were performed.

## Scope and bindings

Reviewed the complete actual five-file Task 5 delta: both new publication files and every change to pipeline_inputs, pipeline_journal and pipeline_worker. Starting HEAD was 62fd437afeac079aacc0177cd4a9710558ae8c80. During review the coordinator committed the separately accepted Task 6 specification clarification as 761a1195f5575bc6689d7eb31cb2a9097a53c755; the five publication files remained unchanged. The separately accepted default-source fix was then committed as 90c8ef6; neither commit changed the reviewed publication files. This is content-bound Task 5 review, not acceptance of that later Task 6 implementation or a whole PR.

Read repository AGENTS, pipeline spec and plan, all thirteen implementation-ledger rulings, prior Task 1Р Р†Р вЂљРІР‚Сљ4 reviews including their final corrective acceptances, and the Task 6 spec-only acceptance. Applied Superpowers review and verification guidance. Original accepted specification/plan canonical bindings were 8de84fe1a6ea7e22f104a2b5812e86bedea97c9363cf0971bbbea5eba0fd0f77 / 4f13c9eb4bf4222a1cdebf5c677b7ed932d8415f386ee9623ade02906b916feb. Current separately accepted clarification bindings are 68f611b225dbb412f3f136f8da1f38b1e217378703fe25a04640580686e6a4db / 107b4f89406dd2c9a3ba1962294f2472d83c335579a9786c3c0a044d3f4882b2. Ledger raw/canonical: e1f5f48a93f4c90914abd6637891852a85060a14f7bca62ea8c1da09d34b41be.

Independently recomputed raw and sha256-utf8-lf-v2 canonical SHA256:

| File | Raw SHA256 | Canonical SHA256 |
| --- | --- | --- |
| task_tower/pipeline_publish.py | b5fb30285671497f539c28cd0b3ffcb76bf9dec88d5f97192ce55f68cbcb66f0 | b5fb30285671497f539c28cd0b3ffcb76bf9dec88d5f97192ce55f68cbcb66f0 |
| tests/test_pipeline_publish.py | 6f1e4ab7a7fbfae1a613d8150888e8350de82b95f23a078b9c21e8a9b76e3498 | 6f1e4ab7a7fbfae1a613d8150888e8350de82b95f23a078b9c21e8a9b76e3498 |
| task_tower/pipeline_inputs.py | a002f0b6c81a79fdc58df83c29391ca8a830ff23a330a6a2668efe320ea50fd2 | a002f0b6c81a79fdc58df83c29391ca8a830ff23a330a6a2668efe320ea50fd2 |
| task_tower/pipeline_journal.py | 016226c4bbaf8431090beeea63d1c91a6c3553cc1be31c6ab840dfe399b0909c | 016226c4bbaf8431090beeea63d1c91a6c3553cc1be31c6ab840dfe399b0909c |
| task_tower/pipeline_worker.py | 95d3eb370b500cd3a9c8000647360168cd8471360e1f0acb3f819b39844de0df | 5f1c7b0ce34048697cef8c4c587c22c67e7994f3dc20773eb01b55906f393a95 |

The actual test environment includes the separately reviewed dispatch_selection default-factory patch: raw b364166a0e399af3e56f3c7ce074d0b91430829a0d4cb9d134b390052ec837f8, canonical 062d52a32a4cc794eb648c80c9d51613b5f118f271abf87d26c6d2969a80badc. That two-file fix is independently accepted in default-source-review.md and committed as 90c8ef6, and is outside this five-file verdict; these tests must not be represented as running its old HEAD version.

## Findings and authority checks

No blocking finding identified in source inspection. Publication obtains actual current journal state through host authority, revalidates private saved policy/profile/pins, current Issue criteria/dependencies and authoritative main, and reconstructs all three current independent receipt bindings. Publisher callback return values do not establish acceptance: the worker ignores the return and reloads actual journal state. Typed journal observation validates URL/number/author and exact immutable task/run/repository/head/base/branch/marker, including on database reload.

Public Markdown is deterministic host projection of accepted receipt/check/supersession facts and limitations. It excludes private paths, raw role prose and logs. Its separately persisted canonical private JSON excludes itself and mutable cards. Final commit F has accepted test checkpoint T as its sole parent, exact attested projection tree/message/content, null contributing executor and the evidence manifest digest. The accepted stage manifest and product digest remain bound to T; the controller's narrow final-checkpoint exception reconstructs F and validates both actual files and product digest. Ordinary mutations cannot acquire that exception. Disabled publication completes only local evidence and ready_for_pr without remote writes.

PR identity is journal minted before creation, with one canonical effect UUID marker and one standalone private-mapped Task-Tower line. Body/title digests are recomputed from deterministic host text, without closing keywords. GitHub response URLs accept repository casing while enforcing HTTPS github.com, exact repository and positive PR number, canonicalizing the recorded URL; path casing, ports, credentials, query/fragment and foreign repositories fail. Head and base repositories/SHA/refs and trusted publisher must match. Lookup is bounded to ten pages of 100, enumerates open/closed PRs and fences duplicate or mismatched results; exact positive adoption cannot authorize a second POST after an unknown result.

Git publication rejects mismatched/ambiguous origin, push URLs, rewriting and unsafe remote/helper/command configuration. It rechecks the branch object and remote ref, uses a private empty hooks path and fixed exact refspec, disables follow-tags, signing and submodule recursion and never forces. Git environment filtering removes caller Git redirection. Durable commit/ref, push and PR intents precede their writes; live freshness is checked again around the irreversible boundaries. Missing or lost observations never permit replay. inspect_effect only reads persisted identity, Git objects/refs or PR GET responses, leaving unknown ownership and journal state intact. This module has no merge, Issue-close PATCH or done-receipt path.

## Independent verification

Runtime: C:/Users/sibiya666/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe. Commands ran from this checkout with real local Git repositories/worktrees and child processes. Every publication ls-remote/push was remapped to a local bare repository and all PR transport used a fake HTTP store; no live publication writes occurred.

**20 tests in 563.389 seconds, OK (zero failures/errors/skips).** Actual command: `& 'C:/Users/sibiya666/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -m unittest tests.test_pipeline_publish -v *> runtime-task5-independent-review.log`.

Additional independent hostile probe (PowerShell here-string piped to the same Python executable with `-`, output runtime-task5-independent-owner-loss.log): instantiate PublicationTests and its real accepted six-role flow, perform final commit and local push, wrap only fake Store.request so its POST first succeeds and then invokes real journal.recover under a positive-dead PID predicate. Assert the actual persisted run becomes unknown, the PR effect remains intent, exactly one POST occurred, inspect_effect returns the exact positive PR observation without changing history, and a later worker tick preserves unknown state and one POST. **PASS**, process output: `PASS independent owner death after POST: one write; durable intent retained; unknown run fenced; exact PR observation read-only; no replay`. Recovery was not replaced; only PID death was deterministically injected.

Two initial reviewer probe attempts failed incorrect probe assertions rather than product behavior: one expected the effect to become unknown even though unknown ownership correctly prevents completion mutation, and one expected an idle tick's return to expose the unclaimed unknown run rather than inspecting its persisted state. Both assertions were corrected with no product changes. The final complete probe passed; the initial attempts are retained in runtime-task5-independent-probe.log and runtime-task5-independent-probe-corrected.log and are not counted as passing evidence.

## Reported evidence and limits

The coordinator separately reported author evidence: current publication 19 tests passed in 607.988 seconds plus final pure contracts 2 passed in 0.005 seconds (20 unique tests total), shared inputs/journal plus three actual worker flows 57 tests in 128.697 seconds OK with one skip, and legacy publication 31 passed in 51.201 seconds. These are reported evidence, not reviewer reruns.

This scoped review does not replace Task 6 watch/controller/credential inheritance implementation acceptance, whole implementation/test acceptance, full-suite or three-OS CI, installed-Codex pilot, exact-head/base whole-PR acceptance or serialized main/postmerge/automatic Issue-closure gates. Local fake publication evidence does not establish remote installed-runtime readiness. Network Git uses the existing synchronous helper without its own timeout; Task 6 must prove contained worker/deadline cancellation and cleanup while publication is blocked. This review verifies freshness gates before new effects and unknown-outcome fencing, and does not claim live-network responsiveness or unattended readiness. Any bound product-content change invalidates this verdict.

Final verification: independently recomputed all five raw bindings after the suite and hostile probe; every value matched the table. No source changes occurred. Builder check: nothing important left within this scoped Task 5 boundary.
