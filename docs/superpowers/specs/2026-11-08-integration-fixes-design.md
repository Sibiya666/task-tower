# Integration handoff fixes

Direct user scope: take all five findings from the integration handoff at
`0ae67c55fec12e059a67d64f8505e15ff64757c8` to accepted Task Tower main.
Canonical work is `tt-uy8` and children `.1` through `.5`. Implementation starts
from the preserved PR119 prototype; its original branch remains unchanged.

## Approach and boundaries

Extend the existing explicit-approved intake, native wrapper and trusted delivery.
Keep Beads as the only task/owner/history engine. A new scheduler, implicit backlog
discovery and generic reuse of Task Tower acceptance for unrelated repositories
would violate the requested route. No external project DB or service is activated.

1. Running intake accepts only append-only approved digests/assignments. Compare
   the exact operator document before expensive credential validation on unchanged
   polls; changed immutable fields fail closed. Keep one Store and foreground loop.
   A late card must traverse real native claim, author, distinct reviewer and saved
   result without manual claim/turn/start. Synthetic integration tests are separate
   from this real pilot evidence.
2. Adoption retains IDs/history, exact title/description, open/unassigned state,
   parents and dependency set, metadata fences and two complete native readbacks.
   Allow external closed blockers only after fresh native verification, including
   subsequent execution checks. Never create or mutate an adopted native task.
3. Trusted per-project native profiles bind exact executable and explicit history
   dialect. Existing event-history defaults stay compatible. Legacy history is not
   converted into invented events; unsupported event closure fails before close.
   The initial `bd --readonly sql` candidate was rejected: 1.0.2 still initializes
   a writable store on that route. Use only the direct Dolt remote reader described
   in [legacy history](../../runtime/legacy-event-reader.md), with exact project
   identity, source/endpoint guards and real disposable proof still required.
4. Trusted immutable delivery policy binds repository, base and delivery mode.
   Task Tower keeps its existing protected PR/main gates. Other repositories may
   receive PR-only owner handoff or a local reviewed result, with verified cleanup;
   these outcomes never become canonical accepted/closed. Config drift is fenced.
5. The PR119 provisioning timeout is authentic, unchanged-base and unreproduced.
   Remove unnecessary provisioning process dependence only with native security
   evidence and the existing five-second bound; preserve production ACL validation.
   Historical cause remains unknown unless discriminating evidence establishes it.

## Acceptance

Focused RED/GREEN checks, real native/security boundaries, exact-source whole-diff
independent review, then final documented full verification through noninteractive
Reslop with raw logs and source receipts. All actual CI, genuine acceptance status,
protected expected-head merge and fresh independent exact-main acceptance precede
owner-only Beads close/history/readback. Missing real external access is reported,
never replaced by fictional acceptance. Mac/project migration is outside scope.
