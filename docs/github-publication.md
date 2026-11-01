# Publishing local postmerge acceptance

The local postmerge watcher can publish its existing accepted decision to GitHub. Add this optional block to its private installation configuration:

```json
"github_publication": {
  "issue_tasks": {"TT-EXAMPLE-001": 9},
  "publisher_account": "your-github-login"
}
```

The repository comes from the watcher's existing configuration. Use the exact mapped Task Tower ID in the Issue's metadata (`legacy_id`, `task_id` or `id`). The publisher verifies the immutable GitHub Issue ID, main ancestry, current source bundle, every configured CI platform, accepted local evidence hashes, pre-review input snapshot and durable journal approve result. It preserves Issue prose, appends a lifecycle receipt, checks the actual API response author, then closes the Issue as completed. Relative evidence names and hashes are public; absolute local paths and raw model logs are excluded.

Publication claims and retry status live separately from local acceptance in the existing journal. Retain that journal during upgrades. Failed or ambiguous network operations retry using the persisted receipt and discover an existing matching comment before posting. A publication retry does not rerun the reviewer. A newer conflicting lifecycle or CI attempt blocks old acceptance; ambiguous ordering requires explicit reconciliation. Published state means the API confirmed the receipt and completed close.

To let books recognize this local receipt, add an explicit account list to that project's private connections entry:

```json
"trusted_publishers": ["your-github-login"]
```

Existing connections default to an empty list and trust no local publisher. Account comparisons are case insensitive. Books derive author identity from GitHub's actual comment `user.login`; JSON author claims and Issue-body done are not attestations. They independently check repository, Issue number and immutable ID, task identity, main ancestry, fresh verified CI, all declared required platforms, approval fields, independent reviewers, input-snapshot shape, and canonical receipt/evidence digests. Historical conflicting lifecycle attempts cannot be bypassed by reposting an old receipt. Old workflow or rejection lifecycle history requires explicit operator reconciliation; the verifier never clears it by accepting a reposted approval. Unknown cross-mode ordering fails closed.

A trusted account's credential holder can attest local review and evidence. The receipt hashes detect alteration and bind the declared evidence; they do not provide anonymous cryptographic proof that the local review occurred. Trust only installation-controlled accounts. Existing Actions workflow artifact verification remains a separate path and does not require this account list.

Refresh books after publication to project the proven done state. Closing an Issue by itself never proves completion. A live rollout must preserve the journal, avoid interrupting an active reviewer, confirm the appended comment and completed Issue state, then run another watcher tick and verify no new comment or review. Automated tests do not establish that live rollout evidence.
