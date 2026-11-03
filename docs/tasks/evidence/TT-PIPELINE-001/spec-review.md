# TT-PIPELINE-001 independent specification and plan acceptance

## Current R1 reacceptance

Verdict: **accepted**, superseding the historical original acceptance below. Freshly reviewed bindings at source base `918554a1e7f6dec10f81a366c1dececa845ff072`:

- Spec: `8de84fe1a6ea7e22f104a2b5812e86bedea97c9363cf0971bbbea5eba0fd0f77`.
- Plan: `4f13c9eb4bf4222a1cdebf5c677b7ed932d8415f386ee9623ade02906b916feb`.

The coordinator identified a real compatibility omission after my original acceptance: rejecting BOM in all product text and applying a 1 MiB cap to every artifact would reject existing required PowerShell and repository assets. The original acceptance is retained as historical and is not current authority. No implementation began under that superseded input.

I reread the complete revised spec, plan constraints/interfaces/callers and unchanged authority/recovery/publication contracts, and independently checked both new file hashes. The revision now distinguishes pure product conversion from designated artifact validation: `canonical_text` preserves BOM, converts CRLF and bare CR to LF, and never rewrites source; `canonical_artifact` additionally rejects BOM. The new `sha256-utf8-lf-v2` product scheme does not redefine legacy task v1 receipts or instruction pins. Product manifest entries record their actual text/raw scheme. The journal, manifest and result schema versions can remain their proposed values: no pipeline implementation or persisted pipeline v1 state exists to migrate, and these schema versions are distinct from the named hashing scheme.

Independent read-only probes of actual Git blobs established:

- `overlay/install-desktop-shortcut.ps1` is 1,218 bytes and begins with UTF-8 BOM. Applying the proposed conversion preserves the BOM, gives equal digests for LF/CRLF variants, and gives a different digest after removing BOM.
- `overlay/assets/room-skins/wings-2.png` is 3,264,500 bytes and fails strict UTF-8 decoding, so it uses the raw scheme and is included under the 16 MiB product cap.
- `overlay/vendor/webview2/sdk/build/native/include/WebView2.h` is 2,881,933 bytes and is strict UTF-8 without binary control bytes, so it uses the product text scheme under the same 16 MiB cap.
- The largest tracked product blob is the 11,476,174-byte ARM64 WebView2 static library, also below 16 MiB. Neither binary assets nor large ordinary source text require a silent exclusion.

The spec and Task 2 now agree on 1 MiB for designated spec/plan/criteria/MD evidence; 16 MiB for every other ordinary product blob, text or binary; and 100,000 paths/16 MiB for the manifest. Raw and canonical lengths must both satisfy their cap; over-limit input parks with explicit size_limit instead of truncation or omission. Named tests cover BOM preservation/difference, source-byte preservation, legacy proof stability, designated-artifact BOM rejection, 4 MiB binary inclusion and the separate limits. These tests remain required implementation evidence, not tests claimed to have run by this design review.

No blocking findings remain. Builder check: **nothing important left**. The previous nonblocking implementation readings and all later independent acceptance gates below remain applicable. This reacceptance is bound only to the new two hashes and does not grant implementation/test/PR/main acceptance.

## Historical original acceptance — superseded by R1

Verdict: **accepted**. This is specification/plan acceptance only, before product implementation; it is not development, test, PR, main or Issue-completion acceptance.

Reviewer: fresh independent `/root/pipeline_spec_acceptance` instance, distinct from the document author. Reviewed source base: `918554a1e7f6dec10f81a366c1dececa845ff072`.

Accepted canonical UTF-8/LF inputs:

- `docs/superpowers/specs/2026-11-01-stage-pipeline-design.md`: `f3d25f1062e50818d084f194dc0e1f0effee836b7244d502d3105afd59f13104`.
- `docs/superpowers/plans/2026-11-01-stage-pipeline.md`: `139bff14faf42e62533b5ee6365b6bbd251191aacf4533ec6aae156fe6d59191`.

Both on-disk hashes independently matched the author's frozen bindings. Changing either input invalidates this verdict.

## Evidence examined

Independently fetched native [Issue #16](https://github.com/Sibiya666/task-tower/issues/16) through the GitHub connector, including its four original criteria, four acceptance lessons and six continuous/parallel execution requirements. Read repository AGENTS, the architecture design, current executor documentation, and actual executor profile/harness/worker, dispatcher, GitHub source/store, connection, task acceptance and reviewer seams. Read the installed Superpowers builder-check prompt. Examined the complete two proposed documents, their cross-file interfaces and verification obligations. No product source was changed or executed by this review.

## Findings

No blocking findings. Builder check: **nothing important left**. The design supplies enough authority, state, input/output, checkpoint, recovery and publication contracts to implement without inventing load-bearing behavior. SQL layout, internal helpers and fixture plumbing remain ordinary builder choices.

- Native Issue coverage is concrete: six fresh roles, independently bound decisions, bounded backward rework, retained reject/supersession history, host checks and immutable input manifests. Completion prose or editable stage cards cannot advance a run.
- The local watch/controller, two slots, conflict skips and automatic refill are implemented scope, with explicit fault tests. They are not deferred wholesale to #18 or confused with active-chat orchestration. Local exclusion deliberately depends on one installation journal; independent databases are not represented as a distributed lock.
- Initial readiness retains genuine dispatcher/dependency verification. Continuation adds a private owner binding rather than weakening legacy eligibility. Policy, pins, Issue identity/criteria, dependencies, foreign lifecycle and authoritative current-main checks are refreshed before effects; stale main parks instead of silently rebasing.
- Private task triples, profiles, connection publishers and remote identity govern publication. No new credential scope, hidden installation or model selection is required. Trusted custom programs' OS access is honestly bounded by trust and mutation checks rather than a false sandbox claim.
- Product/checkpoint inputs exclude host projections and mutable cards without excluding arbitrary documentation or tests. Cards are rejected if changed. Private staging, tree/parent/ref proofs and separately detached review checkpoints avoid accepting a model-supplied commit. Manifests and verdict chains do not hash themselves.
- Commit/push/POST intents precede effects. Ambiguous writes are fenced, including a lost PR response followed by no-match lookup. Unknown process ownership retains slot/component capacity; cancellation and clean parked blockers require positive cleanup before releasing it.
- Host tests use installed argv, exact product bindings, bounded containment and explicit temp/CI limitation handling. Their success remains independently reviewable for coverage. The installed-Codex pilot is separate from custom transport/process fixtures, with honest blocked reporting and no unauthorized remote write.
- PR creation is distinct from #17's merge worker. This Issue's own integration still requires fresh whole-diff exact-head/base acceptance, green three-OS CI, serialized merging, exact-main independent postmerge acceptance and verified automatic closure.

## Implementation readings and verification gates

These are direct readings of the accepted contracts, not requests for new user decisions: prior receipts must be revalidated against their retained immutable checkpoints, rather than requiring a development product to equal the earlier spec-stage product; use a fresh task-specific host-projection directory so historical review evidence is preserved rather than treated as generated output; duplicate/ambiguous private task mappings fail closed; configured check success cannot replace independent coverage judgment. The documented existing instruction-pin revision is an approved declaration backed by actual canonical file hashes, not an automatic claim that an arbitrary directory proves Git provenance.

No tests were run because the accepted change contains design/plan only. Implementation remains gated by the named RED/GREEN, independent task reviews, complete Python suite, current Ubuntu/macOS/Windows Python 3.11 CI, bounded installed-runtime evidence and final independent development/test/PR/main acceptance. This receipt supplies none of those later verdicts.
