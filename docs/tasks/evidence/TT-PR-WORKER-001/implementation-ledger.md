# PR worker implementation contracts

These coordinator rulings refine interfaces inside the accepted design. They grant no external writer authorization, server-policy changes or model authority. Each implementation still requires independent review.

## Policy and read-only journal access

Installed policy accepts only the specification's exact keys and defaults. A normalized task lookup may include a host-derived readiness_reason; this is not an accepted configuration key. Missing actual exclusive-writer authorization remains a merge-readiness blocker. The current chat's task authorization does not establish control over every other main writer.

The journal may expose validated read-only effects(repository, pr_number) and effect(effect_id) accessors alongside get/rows. They read existing immutable intent/observation history; they neither retry an action nor change ownership or fencing.

## Fresh premerge input revisions

Same-PR head/base/input/policy drift invalidates old acceptance. A genuinely new validated input can create an append-only revision while retaining fixed repository, PR, Issue ID and task identity. The prior row must first be stale/rejected/needs_input under the same live owner, with no repository barrier, unresolved intent, running/unknown launch, cancellation or timeout. Identical rejected input never launches another review.

No prior role launch is a clean prelaunch condition. When a role did launch, its actual host observation must prove completion/failure and cleanup; a clean failure is not approval. Missing cleanup remains fenced. The first deadline and cumulative attempts/effects survive every revision. Old receipts/effects remain immutable and cannot authorize the new binding. This is normal new input, not an unknown-effect reset or owner takeover.

## Publication identity and binding

Preserve github_publication.publication_id exactly: SHA-256 of canonical raw v1 receipt including immutable issue_id. The existing lifecycle comment wrapper has a separate body_sha256. Never substitute the wrapper digest as the legacy publication identity or reinterpret its evidence hash schemes.

Each saved publication and individual comment/close effect must share its full repository/PR/Issue/task/head/base/input/policy binding and owner. Validate this before persistence and on database reads, including reciprocal effect references and archived revisions. Cross-repository, cross-PR or stale-revision references must fail without mutation. Actual network/source verification remains the later host controller's responsibility; a structurally valid journal object is not proof that GitHub accepted an action.

## Deferred provenance recovery seam

Task1 deliberately refuses another PR's held barrier, even for the same task. Task5 will add the explicit provenance-bound recovery-followup interface required by the design, after current source and original-main baseline proofs exist. It must preserve original history, private mapping, fresh whole-followup acceptance and unresolved-write fencing. A Boolean original_verified or replacing the old barrier is not that interface. Task1 acceptance does not claim recovery or real-pilot completion.

## Task3P preservation

The bounded pipeline/private-projection/full-profile-bound-review/individual-publication subset received exact-file independent code acceptance and Root-owned full verification: 853 tests, OK with 7 platform/privilege skips, unchanged inputs and confirmed process cleanup. [Task3P acceptance and retained evidence](task3p-acceptance.md) binds the precise candidate and preserved default APIs. Only evidence and bounded README/AGENTS/ledger documentation were added after that run; product/test bytes were preserved.

Task3L is still a CURRENT unmet required original-legacy-source resolver, with existing stage_authority_unverified refusal and no accepting parser. Task3P can feed pipeline-only Tasks4/5 after its own acceptance, but whole Task3/Issue17/Task6 and installed readiness remain unfulfilled. Actual all-writer authorization and nonbypass server-protection pilot gates have not been configured or attested.
