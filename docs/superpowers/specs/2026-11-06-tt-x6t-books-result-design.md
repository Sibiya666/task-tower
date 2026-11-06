# Public Beads result record (tt-x6t)

Proposed design, not implementation or acceptance. Base: `2df4b4c4590ba590e3e83f4ee348915a47f0b152`.

## Original criterion

Deliver exactly one useful bounded Books result: actual Books shows the real scoped
`tt-x6t` identity, owner, source state, dependencies, event chronology and public
result evidence from canonical Beads. Independent spec/plan, developer/test/review,
fresh actual PR head/base acceptance, genuine required status and CI, protected
expected-head merge, exact-main CI and separate independent acceptance precede
canonical completion. Synthetic/static/WIP evidence cannot replace actual Books.

## Approaches

Existing description already serves ordinary prose but does not supply a separate
typed result record. Copying notes or accepting arbitrary public strings/URLs
could disclose private data. Proposed choice: exactly one bounded JSON block with
only typed values; all displayed links derive from repository and bead identity.
This is the coordinator's proposal, pending design approval.

## Input and public projection

Notes may contain exactly one pair of standalone marker lines:
`TASK_TOWER_PUBLIC_RESULT_V1_BEGIN` and `TASK_TOWER_PUBLIC_RESULT_V1_END`.
LF and CRLF marker lines are accepted; marker-like prose outside standalone lines
stays private and is not a marker. The raw enclosed JSON, without truncation, is
at most 4096 UTF-8 bytes, with exactly these fields:
`version` (integer 1), `pr` (integer 1..9007199254740991), `main_sha`
(40 lowercase hexadecimal characters). Reject duplicate keys, unknown keys,
multiple/unmatched markers, non-object JSON, booleans as numbers, invalid UTF-8
and oversized input. Reject NaN, Infinity and unpaired Unicode surrogates.
Notes outside the block never enter the public projection.
No free text, incoming URL, HTML, Markdown execution, paths, review identities,
CI verdict or acceptance assertion is an input field.

Public `result_evidence` is `{status: "missing"}` when absent,
`{status: "unavailable"}` on invalid block, otherwise
`{status: "recorded", version: 1, pr: N, main_sha: SHA}`. No raw error/input.
UI builds only two URLs: same-repository `pull/N`, and
`blob/SHA/docs/beads-results/BEAD.md`. The latter has a fixed public namespace
and uses the already validated bead identity. Existing UI/native URL validators
remain authoritative for navigation. No Actions/local/executable navigation.
Public receipt content is committed, reviewed, factual scope/check information;
it does not predict merge SHA, CI or acceptance. The canonical typed record is
written only after actual exact-main acceptance and points to the receipt at M.

## Behavior and boundaries

The detail block is labelled as a Beads source record, not automatic acceptance.
Missing/unavailable are visible. `closed`, verification, progress, stale and partial
history semantics remain conservative. Compare projected result_evidence between
current row and last journal snapshot: a mismatch retains the task and record but
marks chronology partial. Unrelated private notes changes do not affect this
comparison; absent notes project to missing. Read-only commands, limits, mixed-source behavior
and private configuration boundaries remain unchanged. The Python public envelope,
native bridge and browser policy each allow only this exact nested schema for
Beads entries. Rendering uses textContent and the existing safe-source handler.

Scope: Beads adapter, public envelope, native Books bridge, Books policy/detail UI,
focused Python/JS/native regression coverage and public docs/receipt. No new task
engine, dispatcher, worker, monitor, hooks, installs or configuration/auth changes.

## Verification and delivery

TDD: malformed/duplicate/oversize/Unicode/unknown fields and private sentinels;
valid end-to-end projection; missing/unavailable; safe derived navigation;
unchanged source state, scoped identity, history gaps and mixed-source failures.
Run full CLI unittest inventory and applicable overlay Python/JS tests. Native
bridge harness and native smoke need the separate action-specific authorization
below; do not run them through the ordinary test suite without that permission.
Run actual full runtime PR CI and exact-merge runtime postmerge CI, not docs-only.
Independent whole-diff exact-H/B approval and separate exact-main acceptor are
required; changed head/base invalidates approval. Only then append genuine typed
record to own canonical card and read back. Actual Books observation must show
that record with identity/owner/state/history before guarded close/history readback.

## Native/app authorization still required

Before any native harness/smoke or actual Books observation, provide exact script,
executable, source SHA, allowed effects, timeout, evidence/privacy bounds and stop
conditions to the manager for action-specific user authorization. No private
configuration scan or inferred active source. Until authorization and successful
real observation exist, leave tt-x6t incomplete. This design grants no such action.

## Independent design review

Separate read-only `scope_review` context reviewed the complete proposed spec and
the original accepted map at the base above: no blocking design defect; its parser
and chronology clarifications are incorporated. This is design review only,
not product, PR, native, exact-main or Books acceptance. Human design approval
is pending.
