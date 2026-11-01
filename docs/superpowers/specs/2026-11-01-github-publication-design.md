# Publish local postmerge acceptance to GitHub

The installed local watcher already independently accepted TT-GITHUB-PROJECTS-001 at main merge a788cfd5e507e9fa75abc119a6c2c099a519c497, but Issue 9 remains open. Extend that watcher with an optional GitHub publisher; do not require installation of a self-hosted Actions runner merely to publish a local decision.

## Contract

Python 3.11+, standard library, Windows/macOS/Linux. Reuse existing credentials without saving/logging them. Explicit installation-only configuration maps task IDs to Issue numbers within the configured repository and names the expected publisher account. No inference of an Issue from an untrusted title. Validate Issue legacy ID or explicit Task Tower identity against the configured task.

Only publish a fresh, verified source bundle for an exact main commit with every configured CI platform passed, a validated local done card with all prior independent stages and current evidence hashes, and the matching durable journal approve result. Reject snapshot/result/commit/repository/task mismatches, stale evidence, newer failed/rejected attempts and changed Issue identity. A closed Issue alone never proves acceptance.

Publish an append-only lifecycle receipt, preserving Issue prose. Include repository, Issue, task ID, merge SHA, verified CI identity/platforms, independent reviewer/executor identity, accepted input snapshot and evidence digest plus validated review. Then PATCH only Issue state closed/completed. Check actual API response author against configured publisher before closing. Do not expose private absolute paths, credentials or model request/output logs. Fail closed on malformed remote data; sanitize transport errors.

Publication has its own durable retry state and cross-process claim in the existing local journal. Persist a deterministic publication identity. HTTP errors, lost responses and process restarts must reuse the same acceptance and discover an existing matching receipt before posting again. Do not rerun a model, reopen accepted tasks, or erase rejection history. Expose pending/publishing/failed/published state separately from local acceptance; bounded network requests and lease recovery must not leave a permanently stuck publication. Recheck remote newer lifecycle before every close. No blanket auto-close of unrelated Issues.

## Receipt identity and lifecycle ordering

Persist the exact canonical versioned receipt payload and its SHA-256 before the first network mutation. Bind repository, Issue number and immutable Issue ID, task ID, full merge SHA, source bundle and CI run/attempt identities, required platforms, accepted snapshot hash, evidence manifest of relative names and hashes, independent executor/reviewer identities, and matching approve result. Derive publication identity from immutable accepted inputs; retries must not rebuild it from mutable working files. A comment digest alone is not independent evidence: books still verify authoritative current source and CI. This is trusted credential holder attestation, not cryptographic execution proof.

Validate the actual GitHub author and complete payload for both newly returned and discovered comments before closing. Reconcile bounded paginated comments by publication identity; conflicting payloads or ambiguous matches fail closed. Comments are editable: append-only describes publisher behavior, not GitHub storage immutability. Remote edits must never silently replace the persisted accepted payload during retries.

Publisher eligibility and book projection must apply the same cross-mode lifecycle precedence. A newer verified running, failed, rejected or needs-input attempt supersedes an older done receipt. Reposting an old approval with a newer comment ID cannot supersede a newer attempt. Use authoritative CI run/attempt ordering and GitHub comment IDs for events on the same attempt, never lexical commit order or caller timestamps. Untrusted comments cannot grant done. Ambiguous relevant lifecycle evidence and pagination exhaustion fail closed. This milestone conservatively requires explicit operator reconciliation when another lifecycle identity already exists, including a transition between local and Actions modes; it does not automatically clear older cross-mode histories. This limits availability while retaining the same fail-closed rule in publisher and books.

Immediately before close, revalidate accepted local inputs, source/CI and latest remote lifecycle while owning the publication lease. After an ambiguous PATCH, inspect Issue state and lifecycle before declaring published. GitHub offers no atomic compare-and-close with comment lifecycle: a new event in that interval remains a documented race, and later book refresh must withhold done on newer rejection even if the Issue remains closed. Do not claim cross-API atomicity or automatically reopen an Issue.

## Book trust

GitHub workflow artifact verification remains unchanged. Add a distinct local-publisher receipt type with explicit trusted publisher accounts in private ProjectConnection configuration; default trusts nobody. Use GitHub's actual comment author identity, never an author field supplied in comment JSON. Validate receipt repository/Issue/task/main commit and fresh CI against authoritative APIs. Do not trust Issue-body done, ordinary/untrusted comments or altered proofs. Trusted publisher accounts are an explicit installation trust boundary; their credential holders can attest local review results. Books and Project projection show done for this proven receipt.

## Rollout and acceptance

Independent spec/code/test acceptance plus full tests. Test successful close, wrong mapping/stale/reject/missing CI, API failure/restart without model call, ambiguous comment/close outcomes, publication concurrency and stale remote rejection. Validate actual Issue 9 through the installed watcher only after tests/review: replace its code/config without interrupting an active reviewer, retain journal, confirm GitHub lifecycle comment and closed state, and run a duplicate tick proving no new comment or review. Record exact main SHA and limitations. No manual Issue close is a passing pilot.
