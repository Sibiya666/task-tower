# tt-x6t: public Books result record

This document describes the bounded product result and its verification scope.
It is a public source receipt, not proof of a future merge, CI run or acceptance.

The adapter extracts one explicitly marked, size-bounded JSON block from canonical
Beads notes. Only version, PR integer and main SHA become a typed public record.
Surrounding notes and arbitrary strings/URLs do not enter this field. Books details
show missing/unavailable states or the record with two derived same-repository
references and a statement that the source record does not confirm acceptance.

Identity, owner, source state, dependencies, chronology and stale/partial data
remain source observations. The record does not close a task or turn source closed
into independently accepted. No task engine, worker, monitor or executable/local
navigation is introduced.

The [design](../superpowers/specs/2026-11-06-tt-x6t-books-result-design.md) and
[plan](../superpowers/plans/2026-11-06-tt-x6t-books-result.md) pin the original
criterion and gates. The [format documentation](../local-beads-books.md#public-result-record)
states the exact schema and bounds. Focused adapter/envelope and browser tests
exercise privacy, malformed blocks, byte limits, exact field validation, history
consistency, safe derived actions and unchanged acceptance semantics.

At this receipt's initial preparation, Python adapter/envelope tests (21), Books
policy tests (17), headless Books browser tests (14) and overlay Python tests (18)
passed. Native bridge validation and actual Books observation were still pending
separate action-specific authorization; this statement does not claim either ran.
The versioned PR history and canonical source record must provide actual later
delivery facts. Neither this file nor a `recorded` field verifies those facts.
