# Independent Task 1 implementation review

2026-11-02. Reviewer `/root/groups_policy_acceptance`, distinct from the implementer. **ACCEPTED for Task 1's pure policy boundary at the exact frozen bindings below.** No actionable Critical, Important or Minor finding remains in this scope. This is neither whole-development/TEST acceptance nor PR/main/postmerge/Issue acceptance.

## Reviewed bindings

Checkout `feat/agent-groups`, independently observed HEAD `2bff4f527cc51a0a79ab4e698a9d0e857bd3b86a`. Both new product files were untracked, so this verdict binds their complete bytes rather than a nonexistent committed diff. Read both files in full, repository AGENTS, accepted design and Task 1 plan, preserved R1 specification review, accepted profile/path/pin helpers and applicable independent-review/verification instructions.

Canonical document hashing means UTF-8-sig decode, CRLF/CR to LF, UTF-8 encode, SHA-256. Product raw and canonical hashes are identical.

| Source | SHA-256 |
| --- | --- |
| task_tower/group_policy.py (raw/canonical) | `a770630320c21266829905644e796d9aeccb5b03e3a7ac08de50ab855e61693c` |
| tests/test_group_policy.py (raw/canonical) | `0a8181cc382808df461de9b8f218c4ba94f1bd8852854cf6e925e5c93dd030c1` |
| docs/superpowers/specs/2026-11-02-agent-groups-design.md (canonical) | `b3b5e7eb918622c7ca45761b9313cf266e29d12e81767af89ca3dd42465ec9bd` |
| docs/superpowers/plans/2026-11-02-agent-groups.md (canonical) | `b6a1015ddeaf2c1a60689706f48d9a238d764c0f3854ca66449f82d4072d47b9` |
| docs/tasks/evidence/TT-GROUPS-001/spec-review.md (canonical) | `04aab5223e336739279dd4ab47d7c17e9e1c7e936e8ad123c672399f25fa6d2a` |

## Findings and strengths

Strict private JSON schema rejects duplicate/extra keys, null structures and Boolean integer confusion. UUID, canonical private journal/config/sidecars, existing repository/runner/profile identities, exact six roles and task-specific executor allowlist are validated. Explicit missing/duplicate routes return null bindings and fixed reasons without fabricated delivery. Components cannot widen group ownership; every routed role uses the task's existing profile. The optional accepted-main source grant requires the exact installed profile fingerprint and anchor syntax; absence grants nothing and no source resolution occurs here.

Bindings re-read group bytes, revalidate private checkout/pins and compare immutable normalized task authority. Returned route/binding mutation does not widen future binding authority. Authorization and capacity digests separate only capacity fields; min(group, pipeline) bounds and profile timeout/log limits are retained. Exact source/path/check/publication policy and connection/profile provenance remain bound. Base-update grants remain disabled by default and bounded. Aggregate declarations preserve explicit qualified identities without asserting native relations or accepted child results.

Imports are standard library plus already accepted dispatch/profile/connection helpers. There is no candidate pipeline runtime import, execution runner, SQLite claim, migration, accepted-main fetch/proof, GitHub write or source-authority substitution. The functions supply policy data for later host admission, not execution or acceptance proof.

## Independent verification

Used existing Python `C:/Users/sibiya666/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe` from this checkout.

- `-m unittest tests.test_group_policy tests.test_executor_profiles tests.test_dispatch_selection -v`: **44 tests, OK, 1 existing symlink-privilege skip, 3.341s**. All 16 new group-policy tests passed.
- Twelve additional independently constructed adversarial probes passed: projects/journal/UUID/groups/roles/routes/capacity/grants/aggregates null or Boolean rejection; returned role/route tampering cannot alter a fresh binding; publication scope widening is rejected. These used temporary fixture policy and no production authority.
- `-m unittest discover -s tests -v`: **474 tests, OK, 4 existing symlink-privilege skips, 112.029s**. Fresh full output retained privately at the review runtime's TEMP `tt-groups-review-full.log`.
- Independently matched the five bindings above and observed exact HEAD. Git status before this report showed only the two frozen product files and existing `runtime-escaped-library-freeze.json` untracked; that existing artifact was not modified.

## Declined to judge and remaining gates

- Database installation uniqueness, canonical journal binding persistence, capacity epochs/debt and reservation/ownership enforcement: Tasks 3/4; this module intentionally does not open a database or claim ownership.
- Genuine accepted-main proof, source resolution/base updates and live profile/config reload at effects: later gated host integration; normalized executor/pipeline configuration is the explicit trusted input contract here, not an Issue/model grant.
- Native aggregate children, dependency receipts/cycles and graph freshness: Task 2 and later production graph integration, not a claim made by policy normalization.
- Runtime concurrency, fresh six-role process independence, unattended refill, whole-development/TEST, pilot and PR/main acceptance: later explicit acceptance stages, not established by these tests.

These are explicit plan boundaries, not waived requirements. Before any pipeline integration, Issue16 still requires exact-main CI, independent postmerge acceptance and automatic closure, followed by actual-API/schema audit and affected spec revalidation. This Task 1 verdict permits the coordinator to commit only the exact reviewed product bytes under the established process; it authorizes no runtime integration or merge by itself. Changed product bytes invalidate this verdict.

Reviewer wrote only this requested report; no source/card mutation, commit, push, journal/config change, ACL/auth change or GitHub write was performed.


---

# Issue18 Task1R independent exact-diff review

Reviewer: /root/groups_policy_task1r_review, 2026-11-02; distinct from implementer.

Verdict: APPROVE the two-file pure-policy change at the exact bindings below. No blocking findings. This is task development review, not PR, runtime integration, migration, resource collection, pilot, main or Issue acceptance.

Base/checkout HEAD: cb7a8ee378db4f76515d2a1d11542cf6b7c77585 (feat/agent-groups). Reviewed the complete current working-tree diff relative to HEAD of only:

- task_tower/group_policy.py SHA256 9bbb0c8729ddf08b07c0ef634226dc694b5d0c022d5ae8ef06be8f0569fb087c
- tests/test_group_policy.py SHA256 d794d8574b372869732e0698e3c1bec0a710a2399cb60d90bc4acd9789fdfb87

Requirements: spec docs/superpowers/specs/2026-11-02-agent-groups-design.md SHA256 2b98f00a034878d649315972d77d1316b031a32956df6abcfc37854ded61f2b7; plan docs/superpowers/plans/2026-11-02-agent-groups.md SHA256 138523c0115a618027168a48817af888d72ab46bb654e96db3aa5deb5ca88817. Read repository AGENTS, independent R3 acceptance at parent workspace runtime/groups18-capacity-r3-independent-review.md, and requesting-code-review instructions/template context. using-superpowers expressly exempts dispatched subagents.

The version2 group schema has closed auto/fallback shapes, strict positive nullable signed-64-bit caps, optional null inheritance and no fixed task-count ceiling. Count minima include executor/pipeline historical v1 explicit defaults when participating in v2; group caps narrow routes. Legacy v1 input behavior/defaults remain intact for its historical supported normalized v1 inputs. Exact route/profile/component/source/update-grant authority is retained. Resource envelopes and pool identity participate in authorization; only enumerated capacity controls (including max_parallel) are excluded from authorization and bound into the capacity digest. Alias argv authority cannot split pools, pool caps take minima, and bindings copy the resource grants/pools. No model hints, inferred quotas, launch, claim, journal or pipeline runtime import is introduced.

The executor-v2 and pipeline-v2 dictionaries in tests are synthetic normalized pure-policy fixtures. They do not establish shipped file loader support. Actual loader/runtime integration remains Task3 work blocked on Issue16 exact accepted main, main CI, independent postmerge acceptance and automatic Issue closure. This approval must not be described as removing the shipped v1 executor ceiling or proving actual parallel resource admission.

Independent validation using C:/Users/sibiya666/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe:

- unittest discover -s tests -p test_group_policy.py -v: 39 tests, 5.317s, OK.
- unittest tests.test_group_policy tests.test_executor_profiles tests.test_dispatch_selection -v: 67 tests, 5.717s, OK (1 skip: symlink privilege unavailable).

Author-reported 71 targeted tests/6.405s and full 513 tests/114.023s/4 skips were not reproduced by this reviewer and exact retained output for those runs was not located. The independent scoped checks above are the evidence for this verdict; full-suite evidence remains the coordinator's required verification before integration. No native observation, installed model, external auth, installation or runtime acceptance is implied.

Only this private report was written. No source/docs/card/GitHub edits, commit or push were performed. Any change to either reviewed file hash invalidates this task verdict.

Declined to judge (outside this explicitly assigned two-file Task1R boundary):

- Shipping executor/pipeline v2 file loaders: Task3 blocked integration; dictionaries here are normalized policy fixtures, not loader evidence.
- Host samples, runtime resource arithmetic/leases, migration and concurrent claims: later tasks, with no implementation in this diff.
- PR/main readiness and Issue closure: require their own exact head/base, CI and independent postmerge gates; not granted by this verdict.

Coordinator clarified the author's 71-test command was tests.test_group_policy tests.test_group_graph tests.test_executor_profiles -q. It differs from the reviewer's 67-test required Task1 command above; neither count contradicts the other. The author's full-suite evidence remains author-reported only here.

## Fresh mechanical EOF receipt

APPROVE refreshed binding, 2026-11-02. Product file remains SHA256 9bbb0c8729ddf08b07c0ef634226dc694b5d0c022d5ae8ef06be8f0569fb087c. Current tests/test_group_policy.py is SHA256 e36f5c0ca88ca2c7f5d6e92db75157e866300efbb66de519494790a9ae4726b3.

Independently verified exact old test bytes: replacing the current final LF with CRLF CRLF reconstructs SHA256 d794d8574b372869732e0698e3c1bec0a710a2399cb60d90bc4acd9789fdfb87. Thus the only change since the full review is three EOF newline bytes; executable/test logic is identical. The review and prior independent checks carry to these refreshed exact hashes without redundant execution. All original acceptance scope limits remain in force.
