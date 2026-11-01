# Independent test acceptance — TT-DISPATCH-001

Verdict: ACCEPTED. Reviewer: dispatcher_test_acceptance, distinct from implementation and development reviewers. Bound to the stable source below against base 4dc8e32420e5a9ddfa19852379cf6270ce9702e4. This test-stage verdict does not replace exact-head/base PR acceptance, three-platform CI, exact-main postmerge acceptance or automatic Issue closure.

Independent full verification: Python 3.13 bundled runtime, `python -m unittest discover -s tests -v`, 299 tests in 76.674s, OK (2 existing platform skips). Log: runtime-dispatcher-test-acceptance.log. The 55-file canonical source inventory was collected before and after the complete run and was identical. No production edits, commits or remote changes were made by this reviewer.

Audited actual selector, journal, adapter and CLI tests: strict private authority and aliases; stale remote lifecycle states; canonical/local dependency agreement and malformed/default denial; source-isolated cross-project consumers; spawned-process reservation and submit races; committed-intent process exit before launch followed only by lookup; monotonic accepted state; durable lookup fairness; separate eight-lookup/eight-submit budgets with deferred ninth tasks progressing next tick; revocation/revalidation; bounded managed-file protocol; malformed UTF-8, duplicate keys, oversized/nonregular/hard-linked results; actual timeout/nonzero processes and injected cleanup failure; unsafe/private path boundaries; read-only missing/existing journals and WAL refusal without sidecar changes. Canonical resolved temporary paths are used by helper adapters for macOS compatibility. Existing processes.py/windows_job.py remain unchanged against base.

Additional independent executed counterexamples used genuine project_worker.verified_done, not a permissive verifier: a closed dependency with status done; a closed dependency with forged accepted postmerge stage; and a closed dependency with remote_attempt done/run_id 99 all excluded their consumer with dependency_unverified. An independent recursive directory/file-byte inventory around enabled dry-run and status preserved an existing unknown journal, private config/connections, and nested sentinel files exactly, with no adapter call. The ordinary tests additionally retain WAL files and uncheckpointed acceptance state unchanged while refusing read-only access.

Failure history is retained, not overwritten: earlier development review exposed stale lifecycle, writable read-only WAL behavior, weakened schema constraints, reservation-race budget leakage and missing final-source failure visibility; regression tests and fixes precede this stable passing run. Existing runtime-test-acceptance.log and runtime-test-acceptance-final.log record earlier onboarding-stage failures (252-test unresolved-create replay cases and 255-test injected local publication failure); runtime-test-acceptance-stable.log records that earlier stage's passing rerun. Those earlier logs are not substituted for the dispatcher verdict.

Limits: this local run is Windows; macOS/Linux execution belongs to CI. Process exit after durable reserve simulates the crash boundary without killing an executing submit; the permanently unknown outcome is intentional. The process timeout uses the existing lifecycle implementation; cleanup-failure coverage injects its outcome. No custom adapter can be proven read-only by the dispatcher. GitHub/private revocation after the final check remains non-atomic. No live delivery, development execution, daemon readiness or postmerge claim follows from these tests.

Canonical manifest scheme: sha256-utf8-lf-v1. Decode UTF-8, normalize CRLF and CR to LF, encode UTF-8 without BOM, SHA-256 bytes. Inventory covers all top-level task_tower and tests Python sources plus stable dispatcher/architecture documentation. Mutable task cards and evidence (including this file) are excluded to avoid self-reference.

- AGENTS.md: 5dca4fae766f6c995ef9769b296c2bbdf719e8af8ee60413c6d09024a0f11c7a
- docs/dispatcher.md: 7d53d308e6ee03918275bb58241ee9b50ff0ce62dcc88a95e74e551a84482208
- docs/roadmap.md: dbc8b14afb80c05ee2cb54400297f14a1f09a2ead62062e5dba09ee7676d7f81
- docs/superpowers/plans/2026-11-01-issue-dispatcher.md: fb18a98a61898cd6e0d0c314167e98170783a3d06e06bddaf2ac55faf2538d2c
- docs/superpowers/specs/2026-11-01-issue-dispatcher-design.md: 25650b8545c364d5aa80fa2732e44ea3b6285151e540c9dd0315c6c396d0e36b
- README.md: 2553c2452205e3571dce996fea7b8feb93357fd62d967afccc18a3d8a00a09cd
- task_tower/__init__.py: eaea258ba711f94e330bfd3ceebc64c68d09a13441141fe23c9e39acdc20ba0d
- task_tower/__main__.py: 1021fdfe68d8f948a9a21685986ae4c1d6523a69dab5d39e4d0a0072f6f1f065
- task_tower/books.py: d5e1a55abfa281c4628464f102c16377276681a8a0394ce9499f9a1efc76fab9
- task_tower/bootstrap.py: 14db384f16e38a2365d810b404af51826ef5566ea90ac4f11a554e73295985e7
- task_tower/creation_journal.py: b2fc2f68151f2d63415a727914fe17ec123d4ad64f428eb62274576db1975f51
- task_tower/dispatch_delivery.py: 47c11dd30143d5e80a57c4c900198a17c7c29796d8454090576e8318505700e0
- task_tower/dispatch_selection.py: 1bdf8204ec789a32c89dd6a5b4345fb94b590dfd2c9df8b8ee9b3ead9ce77088
- task_tower/dispatcher.py: 4bad20664806c6d42ad2a3f76f472b83c2db3cd04947bce411373036f5ffafb9
- task_tower/github_publication.py: 1bc796004a6d323c32d928c71de52c9730c5863d22e86606f53276cb2da7c92c
- task_tower/github_source.py: 746ae18cc59ea07ac0b4a3cda5506e9eeaed521a35eab5adacedd52a9252563f
- task_tower/github_tasks.py: 71a44ab56f186468431d5b26919f01d7be96321fe4ce1e49249a37a1a7732c6a
- task_tower/harness.py: 64c8fbbed6b20a9433041bc96b1153822adcebd6572ae2eff4a4bdfe6b06d613
- task_tower/merge_events.py: 90f815b38804ee0956cef009648d56f38ff46792519cd88b507c5fd302fb055b
- task_tower/postmerge_journal.py: b94dc97110a2f2609326e540eab54fba61b18eaff95f657bf2b99c6c8d38b404
- task_tower/postmerge_worker.py: b812501b01e1caa9d390707fed5c698f7526bc6e983a18f4b02db87a9d1822a9
- task_tower/processes.py: 16ed204aa128ea2faadf8135335a1bc42987f151517b2c28453ea60f88a494b6
- task_tower/project_connections.py: 60a300b4275910cf0eee38dfade879d6a9596a36bdd3001928cd8e0d5f55c250
- task_tower/project_onboarding.py: 65dcbdb110a5f8069d3efdc3fc961b0d34013fd3563b189085272d3d9e048f38
- task_tower/project_worker.py: 9cb0002ccf5959220b8a7c20b8f656e3f4983319ff0e4805408d44be6fe0b2cc
- task_tower/projects_board.py: 6e76779d709af09df80ad1dc61937a60a87ab176b1285692dcee8bf719e43d24
- task_tower/readiness.py: 4624ba040a17427714f912055b52b9f524879f00cf3a51fb001f6b0dfc420d28
- task_tower/reviewer.py: 2810012bd71efd529716c32ab7feed13defd3f3cfd0a642a8f5aa0a751ecb534
- task_tower/tasks.py: 15ad94859d7d4a1c88b2b835ae289c52a89ecb9b3abc15b0732fe6c83b457135
- task_tower/windows_job.py: 52f93e53d123bba128714adcf5c1c0836839f4a5f404ecf57d99bbcc8c0c0239
- tests/test_bootstrap.py: fe2e098c45c936be049c7524ac36d9506504f087cc55fb3488570430244ace73
- tests/test_bootstrap_connections.py: e9c7fd1dd9fbb7f49046e427398679b91b46512593090d1b537408caeaccf904
- tests/test_cli.py: 6ff1a79d552ee932e95f8b1cc2cb39161ad3dcc533ba83a668b02464fb0229e6
- tests/test_dispatch_delivery.py: f363113a265563469a75e1cfb68a5a5a9095d1565d41bde060703e4b99d316ea
- tests/test_dispatch_selection.py: ac8a64e9f54ab13b4b8fb1f4e8662c4aeea1d14e9de92185fbbd7d73fcb66345
- tests/test_dispatcher.py: 3001755ea884ea791cb77602e295807b356399d95942133d7c2b7579ebdd4245
- tests/test_github_projects.py: 85bf1628e0a18008bb3a31ecd5c1d3dd0a84db8481b5c7b220457060aefa045e
- tests/test_github_projects_acceptance.py: d78b4730b5192cdc8a687d0fe2ef04c756a45edbc13f97c8f04f512d5e2c4f05
- tests/test_github_publication.py: abcd2bdba6685caf8ff8873c556b6a791fbf1b885b7015c3c5cd264e9248299d
- tests/test_github_publication_acceptance.py: 6e1b166c0ba32c18b02ba31793d94f43000227c46e0cd030d0f39576928733c1
- tests/test_github_source.py: 5b5727d13386710dedb05bad72af637a5f550b177ac7fe778ebaf4887bd5586b
- tests/test_harness.py: 59320df31b38fac94ee8e057664b62982ead1771386dd776bf17aa114ad08753
- tests/test_merge_events.py: 05ddcfcc0fa1388cd21ed5e4a059d51ba0ffe27e36017208e2914ecbc931e61e
- tests/test_postmerge_journal.py: a707ab6a717d8e72df848d827dac447d31f2b38e7ab01d9452651c2b52701fd3
- tests/test_postmerge_worker.py: 1a734f84a44db18d37c7cae6112faad1d8083cf290f00f4037818bf842a1cdc7
- tests/test_processes.py: 59a3715597fd3ff33e3c19bbd8ac0c2a80eba38a072d5cdc9f53d5bda802f9b6
- tests/test_project_onboarding.py: 306b8219fd68381c034c7219e40dfddaa1b76eb04d06b43da3c7f59c65a35e61
- tests/test_project_worker.py: eb63b474bdcc19ba69159462caf20810ddd890e8084383d53e7af8a2835768bc
- tests/test_projects_board.py: 532fc010fe55ea2f89b62fd018cedb423c7aa4fc6e5d1f9a6b51a0d9cdf4f5f2
- tests/test_publication_books.py: fdbb6b750ba7e522c69c4ee12728a47a62c025ce84d65de93e11d08beb85771c
- tests/test_readiness.py: cf2cf7910305fbb125fdec91c5def572748d2223cdd86c1cfd32bb91917e60db
- tests/test_reviewer.py: a7429fe4bfec5c6ecbbfc2ab6b8e6093d62e555ce6a2125db0cc6e672275dd6a
- tests/test_task_cli.py: cbd6268521debad9b5bbae6b7120535b043f0ae6e6d991eb6b756915e763aaad
- tests/test_tasks.py: 799b9c5b7c6d1dcb00442c907c116c92cb3eeaf3235dca69104cfe8e799bcfa7
- tests/test_worker_cli.py: dac98ab97f81e58a524e24029787f5b5c76d76ab4fa13ee5c997278d15080bf7
