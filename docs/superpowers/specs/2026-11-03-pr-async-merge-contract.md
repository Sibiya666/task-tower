# Task4c asynchronous merge: concrete accepted-source seams

This proposed refinement consumes the genuine retained/current context and positive publication implementation. It does not authorize an operator boundary, change server rules, add a synchronous merge fallback or claim controller/pilot readiness. Preserve the accepted PRJournal v1 schemas, effect budget, non-expiring original owner and immutable observations.

## Primary API contract

The official [GitHub OpenAPI description](https://github.com/github/rest-api-description/blob/main/descriptions/api.github.com/api.github.com.json), fetched without credentials on2026-11-03, document SHA25612d2d764fafe2333ffacf967d7191dd933b13ae1ed0f493b3e370e05620fc9b5, defines PUT /repos/{owner}/{repo}/pulls/{pull_number}/merge-async. The bounded extracted200/202/409 schemas are retained in runtime/github-async-openapi-20261103.json. The [REST documentation](https://docs.github.com/en/rest/pulls/pulls#merge-a-pull-request-asynchronously) uses API2026-03-10.

PUT remains exactly {sha:head,merge_method:merge,merge_action:direct_merge,bypass_rules:false}. The API provides expected-head protection, not an expected-base CAS. A new202 response has status pending and details with message, uuid, merge_method, merge_action, expected_head_sha; bypass_rules is optional with API defaultfalse. The official examples omit that optional key. Present values must be strictfalse. Do not rewrite the raw response to pretend an explicit returned field existed.

The current accepted PRSource.merge_result unnecessarily requires the bypass_rules key. Narrowly adjust only its pending detail schema to permit that documented omission/default, preserving every other required field and rejecting extras, true/0/null, foreign UUID, wrong method/action and wrong SHA syntax. The actual effect consumer additionally compares expected_head_sha with its original binding. This read-only syntax compatibility is not independent merge authority: only the actual saved explicitfalse PUT intent and current private/server gates authorize a request.

## Request and original ownership

request_merge must first refuse replay of any already intended merge: prior confirmed/unknown/pending/lost actions are inspectable, never a second PUT. With no prior intent, require the genuine positive retained receipt/current semantic proof, exact acknowledged COMMENT/success identities, fresh actual enabled merge/exclusive-writer policy, current strict server protection and CI, and the actual accepted journal row. Acquire only the actual same-repository/same-binding barrier with the original active owner/PID, then commit the existing merge intent. Recheck genuine private/source/retained proof, exact barrier and live owner/deadline immediately before the one allowed PUT. A slow audit never renews the original deadline.

Drift, cancellation, timeout, lost response,409 or any ambiguity consumes/fences the intent and retains the barrier without fallback/retry. An actor/branch/protection mutation is not a repair. A pre-PUT gate rejection without a prior accepted proof must not acquire a barrier. An already acquired barrier is not silently released after uncertain delivery or owner loss.

## Journal observation compatibility

PRJournal.observe preserves every existing observation field other than status. A pending acknowledgement must therefore store {status:unknown,request_uuid:UUID}, not result:pending: adding an immutable pending result would prevent a later genuine merged result. The saved UUID plus the original explicit method/head/options intent records the asynchronous request, and the row becomes merge_pending through its existing code. Existing schemas need no change.

A202/UUID is never completion. A200 merged response gives only a candidate merge SHA; store an unknown observation with that merge_commit if retained, and independently prove actual PR/main/parents/actor before confirmation. A200 enqueued response remains unknown with result:enqueued and keeps the barrier: it is unsupported queue delivery and cannot later be relabeled merged merely because the PR eventually closes. A409 existing-request UUID is not adopted as a newly owned request, and a lost/expired request never triggers another PUT.

## Read-only completion observation

observe_merge performs only bounded existing source reads. After a merge, the old premerge PR is no longer open and its base branch pointer may have advanced; do not normalize an open-ready snapshot or call it positive premerge proof. Instead reload actual pinned private inputs, validate the configured source/connection and exact task identity, re-resolve the genuine original retained request/confirmed review, and inspect the actual original merge intent/barrier. This authorizes fact observation only, not postmerge acceptance or publication.

For a known owned UUID, use the existing read-only merge_result path and preserve unresolved/failed/enqueued/expired outcomes. Confirm only with the existing merge_observation plus additional coherent PR/task checks: exact repository/PR/head, original task marker and immutable original title/body, expected authenticated publisher actor, exactly [original_base,original_head] parents, matching merge SHA and freshly current main equal to that SHA. A response message or an eventual closed Issue is not proof. Recheck current main and original owner/deadline before recording a confirmed observation. Deadline/cancellation/owner uncertainty never resets counts, transfers ownership or releases the barrier; expired work cannot be resurrected as a fresh execution budget.

The confirmed observation stores the existing complete merge proof and moves only to awaiting_main. Current-main CI, independently bound postmerge review, authenticated receipt publication/Issue closure and verified_done remain Task5 barriers. Metadata inspection under revoked execution pins stays separate from this authenticated effect path. No live source journal migration or role-policy change is introduced.
