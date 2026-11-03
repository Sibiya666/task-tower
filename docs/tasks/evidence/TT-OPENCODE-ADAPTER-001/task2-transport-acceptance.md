# Task2 bounded stdin transport acceptance

Task2 fixed candidate is independently approved; whole Issue21 remains pending. Native OpenCode execution, version/events/resume and installed qualification are not established.

The optional stdin_spec binds exactly path, expected_sha256, expected_bytes and expected_identity; maximum4194304 bytes. The runner validates a single-link regular source, copies/hash-checks its bytes into anonymous private read-only staging before spawn, and closes the original source before the child. Existing calls keep DEVNULL and their result shapes. Windows Job containment, capture, timeout/cancellation and descendant cleanup remain in force.

The [initial independent rejection](task2-transport-review-rejected.md) is retained: constructor cleanup leaked a reader if an inheritance failure was followed by writer-close failure. Fix round1 independently attempts every owner cleanup, preserves the primary error and reports unconfirmed cleanup conservatively. The [scoped independent rereview](task2-transport-rereview.md) approves exact v2 bytes and verifies the reproduced failure plus three new regressions. Focused32 tests5.104s, OK1 existing skip, explicit exit0.

Coordinator-owned full command: python -m unittest discover -s tests -v. Actual835 tests1606.579s, OK(skipped=7), exit0. [Durable completion](task2-full-suite-completion.json) confirms unchanged source, complete nontruncated captures and positive cleanup. stderr SHA25662354994b0e405b239be19c2eb8797b0dd2bdce321e5518cee9f87b6f67be660; immutable runner release7586df4ac2e59316521463b7526089c8314024e4. [Source freeze](task2-transport-source-freeze.json) names all three reviewed files; existing test_executor_processes.py was unchanged and executed. Evidence/document preservation introduces no product/test change and does not justify another full run.

[Actual full60 transport proof](task2-full60-transport.json) verifies all60 approved instruction hashes,357576 normalized source bytes and362380 framed bytes delivered to a controlled Python digest child, stdin SHA2565eb4bb68ab11ff66690d644306f36d5e8029a4075cb937240ceb7c82fa3b6262. This is host transport evidence, distinct from small synthetic portable fixtures. No third-party instruction contents were committed and no native OpenCode/model/probe was invoked.

Task3 event validation/fixed invocation and later qualified foreground integration remain separate reviewed steps. Generic and pipeline role OpenCode admission remains closed.
