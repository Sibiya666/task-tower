# Agent presence and decision waiting

User requested entry/exit animation and hourglasses only for agents waiting for the owner's decision. Preserve other ongoing CLI work in this checkout; changes are restricted to overlay and its documentation/tests.

1. Add regression tests for completion distinct from idle and explicit unresolved input requests. Journal exports metadata only; do not infer questions from message prose or export message bodies. Pending asynchronous requests survive completion and automatic continuation until user input; synchronous requests clear on matching output. New turns alone do not resolve a decision.
2. Add completed/waiting statuses, truthful lifecycle replay including large-log backscan. Unknown/stale must not fabricate completion.
3. Maintain a per-room visual roster across snapshots. New agents walk/fade in; completed or removed agents walk/fade out once, then disappear. Re-entry into an existing scene does not replay the whole room. Reduced-motion skips transitions. Preserve scene tier during the visit.
4. Browser tests cover waiting badge metadata, new/finished/removed agents, expiry and stable snapshots; collector tests cover pending request lifecycle. Run focused suites and native smoke, review independently and restart overlay. No commit/push without a new explicit request.
