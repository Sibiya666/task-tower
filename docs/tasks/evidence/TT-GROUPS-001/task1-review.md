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
