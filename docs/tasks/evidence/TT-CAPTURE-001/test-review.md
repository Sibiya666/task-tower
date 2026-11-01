# TT-CAPTURE-001 independent final test acceptance

Verdict: ACCEPTED for final Issue22 testing against the exact stable inventory below. No unresolved test blocker. This is not exact-head/base PR, main CI, postmerge or Issue-closure acceptance.

Reviewer: independent `/root/capture_test_acceptance`, distinct from implementers. Date: 2026-11-01; worktree `task-tower-capture`, branch `feat/session-capture`. Applied verification-before-completion. Read repository/workspace AGENTS, accepted specification/plan and coordinator scope addenda, Task1 original R1 and accepted re-review, and accepted Task2 review. Inspected complete changed/new sources/tests plus books, authentication backport and documentation.

## Verification

Runtime: `C:/Users/sibiya666/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe`.

Command: `python -m unittest discover -s tests -v`. Exit 0: 348 tests in 76.416 seconds, 2 skipped; no failures/errors.

Canonical inventory was captured immediately before and after the complete subprocess; all 100 stable inputs matched. A previous full run also passed 348 tests/2 skips in 76.806 seconds, but coordinator documentation changes invalidated that earlier whole-input binding. The final run above follows those documentation corrections. Inspected corrected README, AGENTS, dispatcher and architecture status: #14/#24 completed, #15/#22 active, hierarchy UI reserved to #23, no unattended execution claim.

`git diff --check`: exit 0; only ordinary Git line-ending checkout warnings.

Independent ephemeral Python assertion probes: exit 0. Validated input remains detached after caller nested mutation; original/session metadata, lifecycle and queue delimiters survive same-Issue promotion losslessly with exactly one intended serialized marker. Execute-request and promotion add no execution mode, task ID or private authorization. Forged closed/status=done remains unverified through actual lifecycle/completion code without patching verified_done. Mixed parent/sub-issue failures remain explicit unavailable errors while milestone identity remains separate. Replacing registry inode with identical bytes during import returns needs_input with existing canonical Issue, preserves replacement and original CRLF card bytes, and leaves pending provenance. Hardlinked books output cannot replace registry.

Additional independent ephemeral assertions: exit 0. Actual GitHubTasks bounded byte transport with an undiscoverable lost POST response makes exactly one POST across two fresh calls and omits the fake secret from the failure. Actual dispatcher._source forwards a fake existing host token only into its proof reader's Authorization header. No real authentication lookup or remote access used.

Initial forged-done probe failed because the lightweight Store lacked the lifecycle comments endpoint, yielding no books entry. Corrected the ephemeral fixture to return empty comments and reran successfully; no production changes.

## Scope and limits

All 48 capture/CLI/migration tests ran in the complete suite: strict bounded input and inert encoding; Project-first setup; durable payload/intent and unknown-outcome fences; board repair; selected-repository mutation scope; same-Issue promotion drift/convergence; native 404 versus 403/500 errors and qualified parent versus milestone; safe books links; immutable exact-byte migration snapshots, active load_task/evidence compatibility and unchanged import_card API; stale/conflicting sources, alias/descriptor/publication races, pending recovery and cross-process registry updates. Existing worker, publisher, snapshot and real artifact completion-proof tests also passed. This reviewer did not substitute fake True completion approval.

Source links/structured hierarchy data are implemented; #23 rendering, executor and unattended pool are not claimed. Cooperating local locks are not distributed ownership or hostile-filesystem immunity. Cross-host first creation requires serialization, and promotion retains the documented final GET/PATCH external-edit race. No overlay changes; native/browser overlay checks were not run.

No production/test edits, commits, remote writes or child agents. Only this review evidence written in repository; probes and suite logs used system temporary directories. Final PR/main gates remain separate.

## Frozen input binding

Canonical normalization: decode UTF-8 with optional BOM, normalize CRLF/CR to LF, encode UTF-8 without BOM, preserve final newline. Includes every Python source under task_tower/, tests/ and overlay/, README/AGENTS, and docs Markdown excluding docs/tasks. Mutable cards/evidence/private runtime and this file excluded. sourceHash hashes sorted records `path + NUL + canonical SHA-256 + LF`.

sourceHash: `3efb7fa8c94bac2192032b1f8cc7c9ee91b3e922af701f9b4c8deefa464b578c`. Before/after identical: 100 inputs.

| Stable input | Canonical SHA-256 |
|---|---|
| `AGENTS.md` | `c34dde78f9ef4216ca5f85e6b8af3b0503bd6a4bcc3dbc130dd954c1d792ed57` |
| `README.md` | `17077fe3bcbaec56fb5ae107c7fc46d896f909890c6ed420cb91c24706c75c2b` |
| `docs/bootstrap.md` | `ba58cf025bebb5f9eb1c751f52c97fa457d34eb71d7a72ab7a04f3966c8e3fed` |
| `docs/development-process.md` | `d13da41354b40b706d14cdc44c57569c8914500e5f8ba870c7aeadaac3c2bcf0` |
| `docs/dispatcher.md` | `82076f3284e8c4b380a6d32a0b4efc21b5ae8dafb68dae73da857b18d583de00` |
| `docs/github-board.md` | `fc1576f224b6b5e0c87a36c5c842a151e6f9e1165a9f3977ca15d5606460a13e` |
| `docs/github-books.md` | `0da864ae878de40cb5066a505b675a9a636a8d042f71d7f7ff268adc9dab4171` |
| `docs/github-projects.md` | `7137876a257bfa432421ee35f36565e290675258914f76f2dd314f9b929e10db` |
| `docs/github-publication.md` | `00ac095131d564b00fde3733ad6605cdc27b7a66b6b325404592d36642da8cfd` |
| `docs/github-setup.md` | `723dd2f38d502eaf93b4e76b592146b4639486187d0fcddcf3908633479325e2` |
| `docs/ideas/2026-11-01-agent-artifact-museum.md` | `3c55218d8fb630e7b82ef5a1e86988088fdf9b2c3e8fc80ba3c67db848505750` |
| `docs/ideas/2026-11-01-compact-towers-and-scene-position.md` | `1f7caff23b69f3b2458c800f91383b2069727d5d5f80fa29e2f4d80913a69fe8` |
| `docs/merge-events.md` | `77edeed283a7634c456ba2f6ee14919dde39f7ecf6702d0a5ad9a783af93a8f0` |
| `docs/postmerge-worker.md` | `58c2b829e952f499a8ae3fe3bf26a15709c52c54375412ea95919c00a1f91d9e` |
| `docs/readiness.md` | `4ce6df28fbf0b466ac0ccfe2e51e47ce98ee5efe65af49ec0fe0bafe9ad2fd29` |
| `docs/reports/2026-11-01-dialoid-readiness.md` | `41624fe2b5f8d65e0bb143d178cfe6d2f4f033e2d46d2f476dabd22507b4c2a9` |
| `docs/reports/2026-11-01-overlay-integration.md` | `dc2dfb309431e6c497593284939d964edc34a233fcae0c5409bf2fc9583b7538` |
| `docs/reports/2026-11-01-pilot-readiness-development.md` | `790d3b5b9ed49f36d66308ee2d396ddd9fe19cc067f13ba00675dbaea1b4eff0` |
| `docs/roadmap.md` | `8448c15f88a2997d068a24282853271084bd8d7fdb2cde3fcede641d1aa12974` |
| `docs/screenshots/README.md` | `dc49683f60809ba20973abf7ba39db6a0cdd8b4054d6fbdc4e0ec92d7461e726` |
| `docs/session-capture.md` | `af6683473d4e14485a42c7dbfa2af3dba69aee56b221fb87b12203d9156b97bc` |
| `docs/superpowers/plans/2026-11-01-agent-presence.md` | `8ab669bf5cf9f58ec2fd512acc0531dee7f60439b603b309af5296ac03f8f616` |
| `docs/superpowers/plans/2026-11-01-bootstrap-harness.md` | `62f8b4c23abcff94f2b5050bd65cdc989c02c93ee13ac9eb5673114ba7869ad8` |
| `docs/superpowers/plans/2026-11-01-github-projects.md` | `02780c216ddbda2ebfba982f1e54fe1cd818e455c2770d62aefb023ef80492ef` |
| `docs/superpowers/plans/2026-11-01-github-publication.md` | `d11320588981cd3335bfd56234d012c52b840ae59461475ab3e405b3e9f23243` |
| `docs/superpowers/plans/2026-11-01-issue-dispatcher.md` | `fb18a98a61898cd6e0d0c314167e98170783a3d06e06bddaf2ac55faf2538d2c` |
| `docs/superpowers/plans/2026-11-01-merge-event.md` | `45d7a23eaabb3f6ac7a75dc223fb5c39fd174435e687f858f975ae9f46884b24` |
| `docs/superpowers/plans/2026-11-01-overlay-integration.md` | `cdda99ee8f90cb8e37050fa3188c55bcdaf8408d8ffb951d6d0018e26cc83ebc` |
| `docs/superpowers/plans/2026-11-01-pilot-readiness.md` | `fa3d4fda262b8897bb578ba7bf669493c81a20e0916ab76583428f9e633f1fa1` |
| `docs/superpowers/plans/2026-11-01-postmerge-worker.md` | `0726309722af26bed0df11714929a2bec87345744632212d8a57aff88e232019` |
| `docs/superpowers/plans/2026-11-01-project-onboarding.md` | `5e8a5e69869734c2c40e8308713953a1805c29e33dc83e88751a3124540f5959` |
| `docs/superpowers/plans/2026-11-01-scene-position.md` | `6809350e1d4ba7b3cb4a383fc87a3d2d851f091ca6f7fe2e0202fd364fd2e9fa` |
| `docs/superpowers/plans/2026-11-01-session-activity-and-tower-arrivals.md` | `343cf7234c70d8eab0c044ce1abd5f840d752ef00152eafeb5dd04c2b43da157` |
| `docs/superpowers/plans/2026-11-01-session-capture.md` | `52e8a0263b5755cc3acdb36c9824fb74de34e736d7055593262c26502e9ae746` |
| `docs/superpowers/specs/2026-11-01-agent-development-architecture-design.md` | `dc8de3c2d0b8b8551498b3c652f89e4ee32cd903cb7bf5c8c5ce3832199833ac` |
| `docs/superpowers/specs/2026-11-01-bootstrap-harness-design.md` | `086aaee3fb52d3d19795ed9175e8014471d30bafe2fd8b42c46beb71cbca2afe` |
| `docs/superpowers/specs/2026-11-01-github-projects-design.md` | `e65c348dfdacaa3acc5f9ed0f59a9b7d0059dbf7f1a8e9c7d364ff9f3101c69d` |
| `docs/superpowers/specs/2026-11-01-github-publication-design.md` | `4ea57ea6f02473fbc7b27c43c798cdb619d5372d8edc28be06eac662b184d8be` |
| `docs/superpowers/specs/2026-11-01-issue-dispatcher-design.md` | `25650b8545c364d5aa80fa2732e44ea3b6285151e540c9dd0315c6c396d0e36b` |
| `docs/superpowers/specs/2026-11-01-merge-event-design.md` | `5633079991c8eb00644a38fcdd2b15c31398df0000fc5985f1a89d5469634b78` |
| `docs/superpowers/specs/2026-11-01-postmerge-worker-design.md` | `136305ffefffe15193fbcd183c1400e5d585b6f211645b156587ddb2eeb5efc4` |
| `docs/superpowers/specs/2026-11-01-project-onboarding-design.md` | `5481a7debe890f601039dc25f0ad6894ce5859e3db0b5ad76894801d703fa85f` |
| `docs/superpowers/specs/2026-11-01-session-capture-design.md` | `bf601bcd82206b61c85f735be88d87d3ec49e7eafc6b41b701dcd8737db2488c` |
| `overlay/collector.py` | `b1477d262301244687b0729c31b6cd2215a3cfb2c5afe582c309216b889885f2` |
| `overlay/test_collector.py` | `1e4f384d7979d73e596eefb784d66eabd3be501455b39a300fb8a4d140ee1d34` |
| `task_tower/__init__.py` | `eaea258ba711f94e330bfd3ceebc64c68d09a13441141fe23c9e39acdc20ba0d` |
| `task_tower/__main__.py` | `b233be3d4570816c4178d8e3a21af0cea6ac772fb2927eeb8c549a3844f75cdb` |
| `task_tower/books.py` | `d838086f3a340a657b2635f2f559296945f5b2a4b4ece3ece0e82a0c55e30e87` |
| `task_tower/bootstrap.py` | `14db384f16e38a2365d810b404af51826ef5566ea90ac4f11a554e73295985e7` |
| `task_tower/capture.py` | `aecb96e7ae4e9bd8fafbcd85f44ae548a183a4a6ef3a22192247321a93f3f331` |
| `task_tower/capture_cli.py` | `ea41cf183930a513eba501652b2ba80d89b118f58be6eea67c5f5c1f37c19c8e` |
| `task_tower/capture_migration.py` | `d8c5c26d6e7ca8b6be77d1543cd679d8bb38d1440563753f8669a766753c09b7` |
| `task_tower/creation_journal.py` | `c5c6be3332276d038d151d99d101893e00bf1a6638af7a1b64be336d340412e3` |
| `task_tower/dispatch_delivery.py` | `47c11dd30143d5e80a57c4c900198a17c7c29796d8454090576e8318505700e0` |
| `task_tower/dispatch_selection.py` | `1bdf8204ec789a32c89dd6a5b4345fb94b590dfd2c9df8b8ee9b3ead9ce77088` |
| `task_tower/dispatcher.py` | `b070801cf3085362b730b0adc8028ea91b2d56951be9398037ba3e017d9790e4` |
| `task_tower/github_publication.py` | `1bc796004a6d323c32d928c71de52c9730c5863d22e86606f53276cb2da7c92c` |
| `task_tower/github_source.py` | `746ae18cc59ea07ac0b4a3cda5506e9eeaed521a35eab5adacedd52a9252563f` |
| `task_tower/github_tasks.py` | `7a59f38382fb9676536c1307fc863edca331be93cdd2858d3ebcfe8a85911519` |
| `task_tower/harness.py` | `64c8fbbed6b20a9433041bc96b1153822adcebd6572ae2eff4a4bdfe6b06d613` |
| `task_tower/merge_events.py` | `90f815b38804ee0956cef009648d56f38ff46792519cd88b507c5fd302fb055b` |
| `task_tower/postmerge_journal.py` | `b94dc97110a2f2609326e540eab54fba61b18eaff95f657bf2b99c6c8d38b404` |
| `task_tower/postmerge_worker.py` | `b812501b01e1caa9d390707fed5c698f7526bc6e983a18f4b02db87a9d1822a9` |
| `task_tower/processes.py` | `16ed204aa128ea2faadf8135335a1bc42987f151517b2c28453ea60f88a494b6` |
| `task_tower/project_connections.py` | `60a300b4275910cf0eee38dfade879d6a9596a36bdd3001928cd8e0d5f55c250` |
| `task_tower/project_onboarding.py` | `65dcbdb110a5f8069d3efdc3fc961b0d34013fd3563b189085272d3d9e048f38` |
| `task_tower/project_worker.py` | `9cb0002ccf5959220b8a7c20b8f656e3f4983319ff0e4805408d44be6fe0b2cc` |
| `task_tower/projects_board.py` | `6e76779d709af09df80ad1dc61937a60a87ab176b1285692dcee8bf719e43d24` |
| `task_tower/readiness.py` | `4624ba040a17427714f912055b52b9f524879f00cf3a51fb001f6b0dfc420d28` |
| `task_tower/reviewer.py` | `2810012bd71efd529716c32ab7feed13defd3f3cfd0a642a8f5aa0a751ecb534` |
| `task_tower/tasks.py` | `15ad94859d7d4a1c88b2b835ae289c52a89ecb9b3abc15b0732fe6c83b457135` |
| `task_tower/windows_job.py` | `52f93e53d123bba128714adcf5c1c0836839f4a5f404ecf57d99bbcc8c0c0239` |
| `tests/test_bootstrap.py` | `fe2e098c45c936be049c7524ac36d9506504f087cc55fb3488570430244ace73` |
| `tests/test_bootstrap_connections.py` | `e9c7fd1dd9fbb7f49046e427398679b91b46512593090d1b537408caeaccf904` |
| `tests/test_capture.py` | `445e6b294f6c6af74c65b2c329f0b90179b88607d33cb7ffba88511bca5ea7de` |
| `tests/test_capture_cli.py` | `66bbcd3b418b9aab8b1e84403d7cab7a713a7ad692a65f2f6f53f0fd6453be04` |
| `tests/test_capture_migration.py` | `c7b0bb05e5dc32bb2dc9698fba8966fa60d6286fa3ae446b2b8e31c09ef7bdc1` |
| `tests/test_cli.py` | `6ff1a79d552ee932e95f8b1cc2cb39161ad3dcc533ba83a668b02464fb0229e6` |
| `tests/test_dispatch_delivery.py` | `f363113a265563469a75e1cfb68a5a5a9095d1565d41bde060703e4b99d316ea` |
| `tests/test_dispatch_selection.py` | `fb345c3bb32cfe43861028cbac78213e6aff2359be1b03e685a89b27ab854e1c` |
| `tests/test_dispatcher.py` | `041a03f10bd61f5a0a1204875f08c890ef83d2041cfd1261ec82efe562808c6d` |
| `tests/test_github_projects.py` | `85bf1628e0a18008bb3a31ecd5c1d3dd0a84db8481b5c7b220457060aefa045e` |
| `tests/test_github_projects_acceptance.py` | `d78b4730b5192cdc8a687d0fe2ef04c756a45edbc13f97c8f04f512d5e2c4f05` |
| `tests/test_github_publication.py` | `abcd2bdba6685caf8ff8873c556b6a791fbf1b885b7015c3c5cd264e9248299d` |
| `tests/test_github_publication_acceptance.py` | `6e1b166c0ba32c18b02ba31793d94f43000227c46e0cd030d0f39576928733c1` |
| `tests/test_github_source.py` | `5b5727d13386710dedb05bad72af637a5f550b177ac7fe778ebaf4887bd5586b` |
| `tests/test_harness.py` | `59320df31b38fac94ee8e057664b62982ead1771386dd776bf17aa114ad08753` |
| `tests/test_merge_events.py` | `05ddcfcc0fa1388cd21ed5e4a059d51ba0ffe27e36017208e2914ecbc931e61e` |
| `tests/test_postmerge_journal.py` | `a707ab6a717d8e72df848d827dac447d31f2b38e7ab01d9452651c2b52701fd3` |
| `tests/test_postmerge_worker.py` | `1a734f84a44db18d37c7cae6112faad1d8083cf290f00f4037818bf842a1cdc7` |
| `tests/test_processes.py` | `59a3715597fd3ff33e3c19bbd8ac0c2a80eba38a072d5cdc9f53d5bda802f9b6` |
| `tests/test_project_onboarding.py` | `306b8219fd68381c034c7219e40dfddaa1b76eb04d06b43da3c7f59c65a35e61` |
| `tests/test_project_worker.py` | `eb63b474bdcc19ba69159462caf20810ddd890e8084383d53e7af8a2835768bc` |
| `tests/test_projects_board.py` | `532fc010fe55ea2f89b62fd018cedb423c7aa4fc6e5d1f9a6b51a0d9cdf4f5f2` |
| `tests/test_publication_books.py` | `fdbb6b750ba7e522c69c4ee12728a47a62c025ce84d65de93e11d08beb85771c` |
| `tests/test_readiness.py` | `cf2cf7910305fbb125fdec91c5def572748d2223cdd86c1cfd32bb91917e60db` |
| `tests/test_reviewer.py` | `a7429fe4bfec5c6ecbbfc2ab6b8e6093d62e555ce6a2125db0cc6e672275dd6a` |
| `tests/test_task_cli.py` | `cbd6268521debad9b5bbae6b7120535b043f0ae6e6d991eb6b756915e763aaad` |
| `tests/test_tasks.py` | `799b9c5b7c6d1dcb00442c907c116c92cb3eeaf3235dca69104cfe8e799bcfa7` |
| `tests/test_worker_cli.py` | `dac98ab97f81e58a524e24029787f5b5c76d76ab4fa13ee5c997278d15080bf7` |


## Fixture portability re-review — current verdict

Verdict: ACCEPTED for testing against the refreshed inventory below. The previous inventory and results remain historical and are superseded as current bindings. This is still not PR, main/postmerge or Issue-closure acceptance.

CI reported a macOS fixture failure because TemporaryDirectory may return a path below the /var symlink, while production safe_config_path deliberately rejects symlink ancestors before resolution. Independently inspected all four actual edits: fixture roots now resolve immediately in CaptureTests, CaptureCLITests, MigrationTests and the multiprocess registry fixture. This canonicalizes the test-owned temporary workspace before constructing connections/files; it does not resolve user-supplied production inputs or weaken link/reparse/hardlink rejection. The same fixtures still exercise those rejection cases.

Compared all prior accepted canonical input hashes: the only changed prior inputs are AGENTS.md, README.md and the three capture test files. Every task_tower production Python hash is unchanged; git diff against incorporated head 0cc3fc5 also shows no task_tower change. Inspected README/AGENTS merge additions from current overlay main: world settings/art documentation and verification commands, separate from capture behavior. Added stable docs are included in the refreshed inventory. Overlay source is inherited main work; this test gate does not independently re-attest its browser/native acceptance.

Fresh full command: python -m unittest discover -s tests -v. Exit 0: 348 tests in 82.507 seconds, 2 skipped, no failures/errors. All capture tests included. All 103 stable inputs matched before/after.

The runtime/command and canonical inventory algorithm are unchanged. Frozen inventory captured before/after full suite, rechecked again immediately before this append. git diff --check exited 0 (ordinary line-ending warnings only). No production source or tests edited by this reviewer; only this evidence append. No remote writes, commits or children.

macOS execution was not available locally: this verdict confirms the fixture correction and fresh Windows suite, and does not claim a new macOS/Linux CI pass. Required current platform CI and exact head/base acceptance remain separate gates.

Current sourceHash: 8b8c0415f70b8c6bae5148aca1c305e42e686284f36bb65a527a7d912bdd0c70. The inventory contains 103 inputs (the previous 100 plus three merged stable docs).

| Current stable input | Canonical SHA-256 |
|---|---|
| AGENTS.md | 29c2d287fff80873a6b034f1c7cd8f8259b85b744e45a2cf62ae193dae7f4311 |
| README.md | eb42ec82b900bc80e67e8b5234002d664cbc21e52325a6e2a3f3f1799ec688e2 |
| docs/bootstrap.md | ba58cf025bebb5f9eb1c751f52c97fa457d34eb71d7a72ab7a04f3966c8e3fed |
| docs/development-process.md | d13da41354b40b706d14cdc44c57569c8914500e5f8ba870c7aeadaac3c2bcf0 |
| docs/dispatcher.md | 82076f3284e8c4b380a6d32a0b4efc21b5ae8dafb68dae73da857b18d583de00 |
| docs/github-board.md | fc1576f224b6b5e0c87a36c5c842a151e6f9e1165a9f3977ca15d5606460a13e |
| docs/github-books.md | 0da864ae878de40cb5066a505b675a9a636a8d042f71d7f7ff268adc9dab4171 |
| docs/github-projects.md | 7137876a257bfa432421ee35f36565e290675258914f76f2dd314f9b929e10db |
| docs/github-publication.md | 00ac095131d564b00fde3733ad6605cdc27b7a66b6b325404592d36642da8cfd |
| docs/github-setup.md | 723dd2f38d502eaf93b4e76b592146b4639486187d0fcddcf3908633479325e2 |
| docs/ideas/2026-11-01-agent-artifact-museum.md | 3c55218d8fb630e7b82ef5a1e86988088fdf9b2c3e8fc80ba3c67db848505750 |
| docs/ideas/2026-11-01-compact-towers-and-scene-position.md | 1f7caff23b69f3b2458c800f91383b2069727d5d5f80fa29e2f4d80913a69fe8 |
| docs/merge-events.md | 77edeed283a7634c456ba2f6ee14919dde39f7ecf6702d0a5ad9a783af93a8f0 |
| docs/postmerge-worker.md | 58c2b829e952f499a8ae3fe3bf26a15709c52c54375412ea95919c00a1f91d9e |
| docs/readiness.md | 4ce6df28fbf0b466ac0ccfe2e51e47ce98ee5efe65af49ec0fe0bafe9ad2fd29 |
| docs/reports/2026-11-01-dialoid-readiness.md | 41624fe2b5f8d65e0bb143d178cfe6d2f4f033e2d46d2f476dabd22507b4c2a9 |
| docs/reports/2026-11-01-overlay-integration.md | dc2dfb309431e6c497593284939d964edc34a233fcae0c5409bf2fc9583b7538 |
| docs/reports/2026-11-01-pilot-readiness-development.md | 790d3b5b9ed49f36d66308ee2d396ddd9fe19cc067f13ba00675dbaea1b4eff0 |
| docs/reports/2026-11-01-visual-audit.md | 74545e9d7948925c3c7a55c4b533e97f1f663c1ea31c89e304c59e845c938a0b |
| docs/reports/2026-11-01-visual-world.md | c2a8faebd50e1dea28c269259db2beae5565043eaec5d0f16eb90903ed321847 |
| docs/roadmap.md | 8448c15f88a2997d068a24282853271084bd8d7fdb2cde3fcede641d1aa12974 |
| docs/screenshots/README.md | dc49683f60809ba20973abf7ba39db6a0cdd8b4054d6fbdc4e0ec92d7461e726 |
| docs/session-capture.md | af6683473d4e14485a42c7dbfa2af3dba69aee56b221fb87b12203d9156b97bc |
| docs/superpowers/plans/2026-11-01-agent-presence.md | 8ab669bf5cf9f58ec2fd512acc0531dee7f60439b603b309af5296ac03f8f616 |
| docs/superpowers/plans/2026-11-01-bootstrap-harness.md | 62f8b4c23abcff94f2b5050bd65cdc989c02c93ee13ac9eb5673114ba7869ad8 |
| docs/superpowers/plans/2026-11-01-github-projects.md | 02780c216ddbda2ebfba982f1e54fe1cd818e455c2770d62aefb023ef80492ef |
| docs/superpowers/plans/2026-11-01-github-publication.md | d11320588981cd3335bfd56234d012c52b840ae59461475ab3e405b3e9f23243 |
| docs/superpowers/plans/2026-11-01-issue-dispatcher.md | fb18a98a61898cd6e0d0c314167e98170783a3d06e06bddaf2ac55faf2538d2c |
| docs/superpowers/plans/2026-11-01-merge-event.md | 45d7a23eaabb3f6ac7a75dc223fb5c39fd174435e687f858f975ae9f46884b24 |
| docs/superpowers/plans/2026-11-01-overlay-integration.md | cdda99ee8f90cb8e37050fa3188c55bcdaf8408d8ffb951d6d0018e26cc83ebc |
| docs/superpowers/plans/2026-11-01-pilot-readiness.md | fa3d4fda262b8897bb578ba7bf669493c81a20e0916ab76583428f9e633f1fa1 |
| docs/superpowers/plans/2026-11-01-postmerge-worker.md | 0726309722af26bed0df11714929a2bec87345744632212d8a57aff88e232019 |
| docs/superpowers/plans/2026-11-01-project-onboarding.md | 5e8a5e69869734c2c40e8308713953a1805c29e33dc83e88751a3124540f5959 |
| docs/superpowers/plans/2026-11-01-scene-position.md | 6809350e1d4ba7b3cb4a383fc87a3d2d851f091ca6f7fe2e0202fd364fd2e9fa |
| docs/superpowers/plans/2026-11-01-session-activity-and-tower-arrivals.md | 343cf7234c70d8eab0c044ce1abd5f840d752ef00152eafeb5dd04c2b43da157 |
| docs/superpowers/plans/2026-11-01-session-capture.md | 52e8a0263b5755cc3acdb36c9824fb74de34e736d7055593262c26502e9ae746 |
| docs/superpowers/plans/2026-11-01-visual-world.md | 0b4cdefef2f0be323048bd7895f0ac81fdb74839000e1993d3dd24e4fda11255 |
| docs/superpowers/specs/2026-11-01-agent-development-architecture-design.md | dc8de3c2d0b8b8551498b3c652f89e4ee32cd903cb7bf5c8c5ce3832199833ac |
| docs/superpowers/specs/2026-11-01-bootstrap-harness-design.md | 086aaee3fb52d3d19795ed9175e8014471d30bafe2fd8b42c46beb71cbca2afe |
| docs/superpowers/specs/2026-11-01-github-projects-design.md | e65c348dfdacaa3acc5f9ed0f59a9b7d0059dbf7f1a8e9c7d364ff9f3101c69d |
| docs/superpowers/specs/2026-11-01-github-publication-design.md | 4ea57ea6f02473fbc7b27c43c798cdb619d5372d8edc28be06eac662b184d8be |
| docs/superpowers/specs/2026-11-01-issue-dispatcher-design.md | 25650b8545c364d5aa80fa2732e44ea3b6285151e540c9dd0315c6c396d0e36b |
| docs/superpowers/specs/2026-11-01-merge-event-design.md | 5633079991c8eb00644a38fcdd2b15c31398df0000fc5985f1a89d5469634b78 |
| docs/superpowers/specs/2026-11-01-postmerge-worker-design.md | 136305ffefffe15193fbcd183c1400e5d585b6f211645b156587ddb2eeb5efc4 |
| docs/superpowers/specs/2026-11-01-project-onboarding-design.md | 5481a7debe890f601039dc25f0ad6894ce5859e3db0b5ad76894801d703fa85f |
| docs/superpowers/specs/2026-11-01-session-capture-design.md | bf601bcd82206b61c85f735be88d87d3ec49e7eafc6b41b701dcd8737db2488c |
| overlay/collector.py | b1477d262301244687b0729c31b6cd2215a3cfb2c5afe582c309216b889885f2 |
| overlay/test_collector.py | 1e4f384d7979d73e596eefb784d66eabd3be501455b39a300fb8a4d140ee1d34 |
| task_tower/__init__.py | eaea258ba711f94e330bfd3ceebc64c68d09a13441141fe23c9e39acdc20ba0d |
| task_tower/__main__.py | b233be3d4570816c4178d8e3a21af0cea6ac772fb2927eeb8c549a3844f75cdb |
| task_tower/books.py | d838086f3a340a657b2635f2f559296945f5b2a4b4ece3ece0e82a0c55e30e87 |
| task_tower/bootstrap.py | 14db384f16e38a2365d810b404af51826ef5566ea90ac4f11a554e73295985e7 |
| task_tower/capture.py | aecb96e7ae4e9bd8fafbcd85f44ae548a183a4a6ef3a22192247321a93f3f331 |
| task_tower/capture_cli.py | ea41cf183930a513eba501652b2ba80d89b118f58be6eea67c5f5c1f37c19c8e |
| task_tower/capture_migration.py | d8c5c26d6e7ca8b6be77d1543cd679d8bb38d1440563753f8669a766753c09b7 |
| task_tower/creation_journal.py | c5c6be3332276d038d151d99d101893e00bf1a6638af7a1b64be336d340412e3 |
| task_tower/dispatch_delivery.py | 47c11dd30143d5e80a57c4c900198a17c7c29796d8454090576e8318505700e0 |
| task_tower/dispatch_selection.py | 1bdf8204ec789a32c89dd6a5b4345fb94b590dfd2c9df8b8ee9b3ead9ce77088 |
| task_tower/dispatcher.py | b070801cf3085362b730b0adc8028ea91b2d56951be9398037ba3e017d9790e4 |
| task_tower/github_publication.py | 1bc796004a6d323c32d928c71de52c9730c5863d22e86606f53276cb2da7c92c |
| task_tower/github_source.py | 746ae18cc59ea07ac0b4a3cda5506e9eeaed521a35eab5adacedd52a9252563f |
| task_tower/github_tasks.py | 7a59f38382fb9676536c1307fc863edca331be93cdd2858d3ebcfe8a85911519 |
| task_tower/harness.py | 64c8fbbed6b20a9433041bc96b1153822adcebd6572ae2eff4a4bdfe6b06d613 |
| task_tower/merge_events.py | 90f815b38804ee0956cef009648d56f38ff46792519cd88b507c5fd302fb055b |
| task_tower/postmerge_journal.py | b94dc97110a2f2609326e540eab54fba61b18eaff95f657bf2b99c6c8d38b404 |
| task_tower/postmerge_worker.py | b812501b01e1caa9d390707fed5c698f7526bc6e983a18f4b02db87a9d1822a9 |
| task_tower/processes.py | 16ed204aa128ea2faadf8135335a1bc42987f151517b2c28453ea60f88a494b6 |
| task_tower/project_connections.py | 60a300b4275910cf0eee38dfade879d6a9596a36bdd3001928cd8e0d5f55c250 |
| task_tower/project_onboarding.py | 65dcbdb110a5f8069d3efdc3fc961b0d34013fd3563b189085272d3d9e048f38 |
| task_tower/project_worker.py | 9cb0002ccf5959220b8a7c20b8f656e3f4983319ff0e4805408d44be6fe0b2cc |
| task_tower/projects_board.py | 6e76779d709af09df80ad1dc61937a60a87ab176b1285692dcee8bf719e43d24 |
| task_tower/readiness.py | 4624ba040a17427714f912055b52b9f524879f00cf3a51fb001f6b0dfc420d28 |
| task_tower/reviewer.py | 2810012bd71efd529716c32ab7feed13defd3f3cfd0a642a8f5aa0a751ecb534 |
| task_tower/tasks.py | 15ad94859d7d4a1c88b2b835ae289c52a89ecb9b3abc15b0732fe6c83b457135 |
| task_tower/windows_job.py | 52f93e53d123bba128714adcf5c1c0836839f4a5f404ecf57d99bbcc8c0c0239 |
| tests/test_bootstrap.py | fe2e098c45c936be049c7524ac36d9506504f087cc55fb3488570430244ace73 |
| tests/test_bootstrap_connections.py | e9c7fd1dd9fbb7f49046e427398679b91b46512593090d1b537408caeaccf904 |
| tests/test_capture.py | 92997f5da84d2fc8ed0078fdbc119b852fb94a74e5b77820b28bf0cf660af830 |
| tests/test_capture_cli.py | 8f87bb0cff1bee4a1ca041141e557bdf54cfa50fb113f727c39e45b06298fec8 |
| tests/test_capture_migration.py | 60fbd21c816b35402dab3f62d07553a6cb2c68759f61f9c23588d6b23aa289b3 |
| tests/test_cli.py | 6ff1a79d552ee932e95f8b1cc2cb39161ad3dcc533ba83a668b02464fb0229e6 |
| tests/test_dispatch_delivery.py | f363113a265563469a75e1cfb68a5a5a9095d1565d41bde060703e4b99d316ea |
| tests/test_dispatch_selection.py | fb345c3bb32cfe43861028cbac78213e6aff2359be1b03e685a89b27ab854e1c |
| tests/test_dispatcher.py | 041a03f10bd61f5a0a1204875f08c890ef83d2041cfd1261ec82efe562808c6d |
| tests/test_github_projects.py | 85bf1628e0a18008bb3a31ecd5c1d3dd0a84db8481b5c7b220457060aefa045e |
| tests/test_github_projects_acceptance.py | d78b4730b5192cdc8a687d0fe2ef04c756a45edbc13f97c8f04f512d5e2c4f05 |
| tests/test_github_publication.py | abcd2bdba6685caf8ff8873c556b6a791fbf1b885b7015c3c5cd264e9248299d |
| tests/test_github_publication_acceptance.py | 6e1b166c0ba32c18b02ba31793d94f43000227c46e0cd030d0f39576928733c1 |
| tests/test_github_source.py | 5b5727d13386710dedb05bad72af637a5f550b177ac7fe778ebaf4887bd5586b |
| tests/test_harness.py | 59320df31b38fac94ee8e057664b62982ead1771386dd776bf17aa114ad08753 |
| tests/test_merge_events.py | 05ddcfcc0fa1388cd21ed5e4a059d51ba0ffe27e36017208e2914ecbc931e61e |
| tests/test_postmerge_journal.py | a707ab6a717d8e72df848d827dac447d31f2b38e7ab01d9452651c2b52701fd3 |
| tests/test_postmerge_worker.py | 1a734f84a44db18d37c7cae6112faad1d8083cf290f00f4037818bf842a1cdc7 |
| tests/test_processes.py | 59a3715597fd3ff33e3c19bbd8ac0c2a80eba38a072d5cdc9f53d5bda802f9b6 |
| tests/test_project_onboarding.py | 306b8219fd68381c034c7219e40dfddaa1b76eb04d06b43da3c7f59c65a35e61 |
| tests/test_project_worker.py | eb63b474bdcc19ba69159462caf20810ddd890e8084383d53e7af8a2835768bc |
| tests/test_projects_board.py | 532fc010fe55ea2f89b62fd018cedb423c7aa4fc6e5d1f9a6b51a0d9cdf4f5f2 |
| tests/test_publication_books.py | fdbb6b750ba7e522c69c4ee12728a47a62c025ce84d65de93e11d08beb85771c |
| tests/test_readiness.py | cf2cf7910305fbb125fdec91c5def572748d2223cdd86c1cfd32bb91917e60db |
| tests/test_reviewer.py | a7429fe4bfec5c6ecbbfc2ab6b8e6093d62e555ce6a2125db0cc6e672275dd6a |
| tests/test_task_cli.py | cbd6268521debad9b5bbae6b7120535b043f0ae6e6d991eb6b756915e763aaad |
| tests/test_tasks.py | 799b9c5b7c6d1dcb00442c907c116c92cb3eeaf3235dca69104cfe8e799bcfa7 |
| tests/test_worker_cli.py | dac98ab97f81e58a524e24029787f5b5c76d76ab4fa13ee5c997278d15080bf7 |
