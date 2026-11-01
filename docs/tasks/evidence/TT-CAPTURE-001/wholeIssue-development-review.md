# TT-CAPTURE-001 whole Issue development review

Verdict: ACCEPTED for the current complete Issue22 development/testing source set. No unresolved blocking source findings. This is not final integration/PR/main/postmerge/Issue-closure acceptance.

Reviewer: independent `/root/capture_migration_review`, distinct from implementer. Date: 2026-11-01. Branch `feat/session-capture`; worktree `task-tower-capture`.

Canonical hashing: decode UTF-8 with optional BOM, normalize CRLF/CR to LF, encode UTF-8 without BOM, preserve final-newline state. sourceHash hashes sorted records `path + NUL + canonical SHA-256 + LF`. Runtime/private state, mutable TaskCards and evidence are excluded.

Inspected the complete actual Issue22 source/test/docs diff against accepted spec/plan, existing import_card, legacy load_task/worker/publisher contracts, private safe paths, CreationJournal and Task1 accepted R1 record. Migration imports the detached bounded exact-byte snapshot through unchanged import_card; original source remains byte-identical and historical evidence hashes are never regenerated. Registry is provenance-only, persists pending digest before POST and uses original path/hash/descriptor rechecks plus local cross-process locking and CAS publication. Source/target drift stops visibly; interrupted registration reuses existing import journal identity rather than recreating. Input/private-state aliases and hardlinks fail closed. Books preserve canonical Issue identity, expose stale/pending status without private paths, and visibly report missing mapped canonical Issues; source errors do not become empty success.

Task1 interoperability retains strict marker-inert typed original/session payloads, stable journal binding and native relation projection. R1 parent-404 fix remains accepted; 403/500 remain unavailable. Capture intent never grants private execution authority or verified completion. CLI error output omits raw payload/transport secrets. No runtime authorization weakening was found.

Cross-host first-create serialization, cooperating local filesystem race detection (not a hostile OS sandbox), and external promotion-edit serialization/final GET-PATCH residual race remain explicit documented limits. Issue23 owns hierarchy rendering. Coordinator README/AGENTS/roadmap integration and future exact head/base PR, CI, main/postmerge and Issue closure acceptance remain outstanding gates.

Independent verification on the reviewed source:

- Runtime `C:/Users/sibiya666/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe`.
- `python -m unittest discover -s tests -p 'test_capture*.py' -v`: exit 0; 48 tests, 3.057 seconds.
- `python -m unittest discover -s tests -v`: exit 0; 347 tests, 2 skipped, 77.246 seconds.
- `git diff --check`: exit 0.
- Independent negative probes (exit 0): delete original during import; replace registry inode with identical bytes during import; books output hardlink alias to registry; actual GitHubTasks transport loses first POST with no discoverable Issue, then retries. Asserted recoverable identity/stale or pending state, no changed-target overwrite, durable source digest, secret-safe exception and exactly one POST across both attempts.

No production/test edits, remote access, commits or child agents. Only review evidence written; temporary local suite log removed.

Task1 R1 history is retained in `task1-review.md`; Task2 detailed current verdict is in `task2-review.md`. Coordinator integration edits will invalidate affected bindings and require refreshed review.

Whole sourceHash: `24fe779ae48a5ef8b11edfb07889a70604c89610996c0739b5f68b98c0637d59`.

| Stable input | Canonical SHA-256 |
|---|---|
| `docs/github-books.md` | `0da864ae878de40cb5066a505b675a9a636a8d042f71d7f7ff268adc9dab4171` |
| `docs/session-capture.md` | `af6683473d4e14485a42c7dbfa2af3dba69aee56b221fb87b12203d9156b97bc` |
| `docs/superpowers/plans/2026-11-01-session-capture.md` | `047a5d85d56a7adca4af22280e28910d5a90226978516616c36c35443662f7a6` |
| `docs/superpowers/specs/2026-11-01-session-capture-design.md` | `fee62c2da3faee0359daf8ccfb07539251df30e1afe78b5bec9e1a625ce096ba` |
| `task_tower/__main__.py` | `b233be3d4570816c4178d8e3a21af0cea6ac772fb2927eeb8c549a3844f75cdb` |
| `task_tower/books.py` | `d838086f3a340a657b2635f2f559296945f5b2a4b4ece3ece0e82a0c55e30e87` |
| `task_tower/capture.py` | `aecb96e7ae4e9bd8fafbcd85f44ae548a183a4a6ef3a22192247321a93f3f331` |
| `task_tower/capture_cli.py` | `ea41cf183930a513eba501652b2ba80d89b118f58be6eea67c5f5c1f37c19c8e` |
| `task_tower/capture_migration.py` | `d8c5c26d6e7ca8b6be77d1543cd679d8bb38d1440563753f8669a766753c09b7` |
| `task_tower/creation_journal.py` | `c5c6be3332276d038d151d99d101893e00bf1a6638af7a1b64be336d340412e3` |
| `task_tower/github_tasks.py` | `7a59f38382fb9676536c1307fc863edca331be93cdd2858d3ebcfe8a85911519` |
| `tests/test_capture.py` | `445e6b294f6c6af74c65b2c329f0b90179b88607d33cb7ffba88511bca5ea7de` |
| `tests/test_capture_cli.py` | `66bbcd3b418b9aab8b1e84403d7cab7a713a7ad692a65f2f6f53f0fd6453be04` |
| `tests/test_capture_migration.py` | `c7b0bb05e5dc32bb2dc9698fba8966fa60d6286fa3ae446b2b8e31c09ef7bdc1` |

## Final coordinator integration re-review (current verdict)

Verdict: CHANGES REQUIRED pending R2 documentation reconciliation. Earlier development/testing acceptance remains historical for its exact source set; this is the current expanded whole-diff integration verdict.

R2 (P2, open): README.md dispatcher paragraph, AGENTS.md Project-first setup, and docs/dispatcher.md opening still say #14 remains current and #15 is next, contradicting their refreshed roadmap/current parallel work. AGENTS.md bookshelf paragraph also retains #22/#23 rendering ownership despite the now-implemented #22 data projection and #23 renderer boundary. Reconcile these lines before final integration acceptance. No production blockers identified.

Scope review: accepted spec/plan integration addenda explicitly permit the process document and coordinator documentation reconciliation plus the narrow dispatcher authentication-source backport. Inspected the entire actual integration diff. `_source` only resolves existing noninteractive host credentials and forwards them to the existing GitHubSource; proof requirements, private authorization, adapter identity-only payload and verifier remain unchanged. No executor, background pool, new scopes or credential grants are shipped. Process documentation clearly distinguishes active-chat parallel work from future #16/#18/#19 persistent orchestration.

Fresh independent `python -m unittest discover -s tests -p test_dispatcher.py -v` exited 0: 14 tests, 1.009 seconds. Prior independent full 347-test run remains recorded above for its earlier source. The expanded 348-test suite is being verified independently by the final testing acceptor; this reviewer does not re-attest that pending run.

Current expanded sourceHash: `d3e6acd6271ca6137d15bba96606528b2b0f79c8b82eee47264a7a6e237a2b3a`. Canonical normalization is as stated above. Any R2 fix invalidates these affected current bindings and requires a refreshed supplement.

| Current expanded stable input | Canonical SHA-256 |
|---|---|
| `AGENTS.md` | `35e2ff2967026c93db966bbeb1fb66035ad70f44bb7079a5f10a02aab53df99e` |
| `README.md` | `17077fe3bcbaec56fb5ae107c7fc46d896f909890c6ed420cb91c24706c75c2b` |
| `docs/development-process.md` | `d13da41354b40b706d14cdc44c57569c8914500e5f8ba870c7aeadaac3c2bcf0` |
| `docs/dispatcher.md` | `82076f3284e8c4b380a6d32a0b4efc21b5ae8dafb68dae73da857b18d583de00` |
| `docs/github-books.md` | `0da864ae878de40cb5066a505b675a9a636a8d042f71d7f7ff268adc9dab4171` |
| `docs/roadmap.md` | `8448c15f88a2997d068a24282853271084bd8d7fdb2cde3fcede641d1aa12974` |
| `docs/session-capture.md` | `af6683473d4e14485a42c7dbfa2af3dba69aee56b221fb87b12203d9156b97bc` |
| `docs/superpowers/plans/2026-11-01-session-capture.md` | `52e8a0263b5755cc3acdb36c9824fb74de34e736d7055593262c26502e9ae746` |
| `docs/superpowers/specs/2026-11-01-session-capture-design.md` | `bf601bcd82206b61c85f735be88d87d3ec49e7eafc6b41b701dcd8737db2488c` |
| `task_tower/__main__.py` | `b233be3d4570816c4178d8e3a21af0cea6ac772fb2927eeb8c549a3844f75cdb` |
| `task_tower/books.py` | `d838086f3a340a657b2635f2f559296945f5b2a4b4ece3ece0e82a0c55e30e87` |
| `task_tower/capture.py` | `aecb96e7ae4e9bd8fafbcd85f44ae548a183a4a6ef3a22192247321a93f3f331` |
| `task_tower/capture_cli.py` | `ea41cf183930a513eba501652b2ba80d89b118f58be6eea67c5f5c1f37c19c8e` |
| `task_tower/capture_migration.py` | `d8c5c26d6e7ca8b6be77d1543cd679d8bb38d1440563753f8669a766753c09b7` |
| `task_tower/creation_journal.py` | `c5c6be3332276d038d151d99d101893e00bf1a6638af7a1b64be336d340412e3` |
| `task_tower/dispatcher.py` | `b070801cf3085362b730b0adc8028ea91b2d56951be9398037ba3e017d9790e4` |
| `task_tower/github_tasks.py` | `7a59f38382fb9676536c1307fc863edca331be93cdd2858d3ebcfe8a85911519` |
| `tests/test_capture.py` | `445e6b294f6c6af74c65b2c329f0b90179b88607d33cb7ffba88511bca5ea7de` |
| `tests/test_capture_cli.py` | `66bbcd3b418b9aab8b1e84403d7cab7a713a7ad692a65f2f6f53f0fd6453be04` |
| `tests/test_capture_migration.py` | `c7b0bb05e5dc32bb2dc9698fba8966fa60d6286fa3ae446b2b8e31c09ef7bdc1` |
| `tests/test_dispatcher.py` | `041a03f10bd61f5a0a1204875f08c890ef83d2041cfd1261ec82efe562808c6d` |

## R2 resolution and final frozen integration review (CURRENT)

Verdict: ACCEPTED for whole Issue22 development on the expanded final frozen source/docs/spec/plan manifest below. No unresolved blocking findings. This supersedes the R2 changes-required verdict for this exact source set only; all prior manifests, findings and test history are retained above. It is not PR head/base, exact-main/postmerge or Issue-closure acceptance.

R2 resolved: independently inspected the final README, AGENTS and dispatcher documentation diffs. All stale #14-current/#15-next claims are removed; #24/#14 are described as accepted/closed and #15/#22 as independent parallel workstreams. AGENTS now assigns hierarchy rendering only to #23 and distinguishes implemented structured capture data. The architecture status header now makes the same correction without changing the target architecture or claiming implementation of its executor, pool or night mode. Process/roadmap documentation preserves serialized merge/main acceptance, explicit project authorization and the active-chat versus persistent #16/#18/#19 boundary. No false hierarchy-renderer or unattended-pool capability claim was found.

The bounded integration scope remains the accepted capture/migration feature, coordinator process/capability documentation and existing-authentication dispatcher source backport. Hash comparison independently confirms every Python production/test input is unchanged from this reviewer's previous expanded authentication-backport review. Its 14-test independent dispatcher verification, original 48-test focused capture verification and original full 347-test/2-skip run remain valid as recorded for their source sets; this docs-only R2 supplement does not claim a new full-suite run. Final testing acceptor is independently rerunning the frozen 348-test suite. No source edits, remote calls, commits or child agents were used for this re-review.

Current expanded sourceHash (22 inputs): `9547c2acb484d8d1690b3a3dd888b0fff13da95615662e95b35fb0dda10d0b69`. Canonical UTF-8/LF algorithm is as stated above; evidence and mutable/private runtime state remain excluded. Changed source/base/head invalidates affected acceptance and requires refresh before integration.

| CURRENT final stable input | Canonical SHA-256 |
|---|---|
| `AGENTS.md` | `c34dde78f9ef4216ca5f85e6b8af3b0503bd6a4bcc3dbc130dd954c1d792ed57` |
| `README.md` | `17077fe3bcbaec56fb5ae107c7fc46d896f909890c6ed420cb91c24706c75c2b` |
| `docs/development-process.md` | `d13da41354b40b706d14cdc44c57569c8914500e5f8ba870c7aeadaac3c2bcf0` |
| `docs/dispatcher.md` | `82076f3284e8c4b380a6d32a0b4efc21b5ae8dafb68dae73da857b18d583de00` |
| `docs/github-books.md` | `0da864ae878de40cb5066a505b675a9a636a8d042f71d7f7ff268adc9dab4171` |
| `docs/roadmap.md` | `8448c15f88a2997d068a24282853271084bd8d7fdb2cde3fcede641d1aa12974` |
| `docs/session-capture.md` | `af6683473d4e14485a42c7dbfa2af3dba69aee56b221fb87b12203d9156b97bc` |
| `docs/superpowers/plans/2026-11-01-session-capture.md` | `52e8a0263b5755cc3acdb36c9824fb74de34e736d7055593262c26502e9ae746` |
| `docs/superpowers/specs/2026-11-01-agent-development-architecture-design.md` | `dc8de3c2d0b8b8551498b3c652f89e4ee32cd903cb7bf5c8c5ce3832199833ac` |
| `docs/superpowers/specs/2026-11-01-session-capture-design.md` | `bf601bcd82206b61c85f735be88d87d3ec49e7eafc6b41b701dcd8737db2488c` |
| `task_tower/__main__.py` | `b233be3d4570816c4178d8e3a21af0cea6ac772fb2927eeb8c549a3844f75cdb` |
| `task_tower/books.py` | `d838086f3a340a657b2635f2f559296945f5b2a4b4ece3ece0e82a0c55e30e87` |
| `task_tower/capture.py` | `aecb96e7ae4e9bd8fafbcd85f44ae548a183a4a6ef3a22192247321a93f3f331` |
| `task_tower/capture_cli.py` | `ea41cf183930a513eba501652b2ba80d89b118f58be6eea67c5f5c1f37c19c8e` |
| `task_tower/capture_migration.py` | `d8c5c26d6e7ca8b6be77d1543cd679d8bb38d1440563753f8669a766753c09b7` |
| `task_tower/creation_journal.py` | `c5c6be3332276d038d151d99d101893e00bf1a6638af7a1b64be336d340412e3` |
| `task_tower/dispatcher.py` | `b070801cf3085362b730b0adc8028ea91b2d56951be9398037ba3e017d9790e4` |
| `task_tower/github_tasks.py` | `7a59f38382fb9676536c1307fc863edca331be93cdd2858d3ebcfe8a85911519` |
| `tests/test_capture.py` | `445e6b294f6c6af74c65b2c329f0b90179b88607d33cb7ffba88511bca5ea7de` |
| `tests/test_capture_cli.py` | `66bbcd3b418b9aab8b1e84403d7cab7a713a7ad692a65f2f6f53f0fd6453be04` |
| `tests/test_capture_migration.py` | `c7b0bb05e5dc32bb2dc9698fba8966fa60d6286fa3ae446b2b8e31c09ef7bdc1` |
| `tests/test_dispatcher.py` | `041a03f10bd61f5a0a1204875f08c890ef83d2041cfd1261ec82efe562808c6d` |

## Current-main incorporation and macOS fixture correction (CURRENT)

Verdict: ACCEPTED for current whole Issue22 development against the refreshed 22-input manifest below. No unresolved blocking findings. Earlier 9547c2ac manifest and R1/R2 history remain preserved as historical exact-source verdicts. This supplement does not substitute for final testing, fresh PR exact head/base or postmerge/main acceptance.

Reviewed the four fixture-only edits across tests/test_capture.py, tests/test_capture_cli.py and tests/test_capture_migration.py: resolve the trusted TemporaryDirectory base before constructing fixture paths or subprocess arguments. macOS /var temporary roots can be symlink aliases; canonicalizing a test-owned root preserves the intended regular canonical-path setup while production safe_config_path continues rejecting user-supplied symlink/reparse paths. No path guard, authorization, production source, assertions or negative-path tests were weakened. Production hashes are identical to prior accepted manifest. The independent testing acceptor owns fresh focused/full execution; no new test-run result is asserted by this document-only review.

Reviewed README/AGENTS changes incorporated from already accepted current main 8c316b7 via merge 0cc3fc5: overlay world/lighting/weather/inactive settings and their verification commands are retained separately from capture. Capture capability, private authorization, #23 hierarchy-renderer ownership, active-chat versus future persistent pool boundary and serialized integration gates remain consistent. This accepts compatibility of the integrated documentation with Issue22, not a new independent overlay implementation acceptance. Canonical comparison confirms only README, AGENTS and the three fixture files changed among the prior 22 inputs.

Current sourceHash: `d0e73aa33a484b3380df529ab33f9bed0185787ee03fc14cdb0440aa85306c5e`. Canonical UTF-8/LF hashing follows the algorithm above; mutable task cards, evidence and runtime state remain excluded.

| CURRENT stable input | Canonical SHA-256 |
|---|---|
| `AGENTS.md` | `29c2d287fff80873a6b034f1c7cd8f8259b85b744e45a2cf62ae193dae7f4311` |
| `README.md` | `eb42ec82b900bc80e67e8b5234002d664cbc21e52325a6e2a3f3f1799ec688e2` |
| `docs/development-process.md` | `d13da41354b40b706d14cdc44c57569c8914500e5f8ba870c7aeadaac3c2bcf0` |
| `docs/dispatcher.md` | `82076f3284e8c4b380a6d32a0b4efc21b5ae8dafb68dae73da857b18d583de00` |
| `docs/github-books.md` | `0da864ae878de40cb5066a505b675a9a636a8d042f71d7f7ff268adc9dab4171` |
| `docs/roadmap.md` | `8448c15f88a2997d068a24282853271084bd8d7fdb2cde3fcede641d1aa12974` |
| `docs/session-capture.md` | `af6683473d4e14485a42c7dbfa2af3dba69aee56b221fb87b12203d9156b97bc` |
| `docs/superpowers/plans/2026-11-01-session-capture.md` | `52e8a0263b5755cc3acdb36c9824fb74de34e736d7055593262c26502e9ae746` |
| `docs/superpowers/specs/2026-11-01-agent-development-architecture-design.md` | `dc8de3c2d0b8b8551498b3c652f89e4ee32cd903cb7bf5c8c5ce3832199833ac` |
| `docs/superpowers/specs/2026-11-01-session-capture-design.md` | `bf601bcd82206b61c85f735be88d87d3ec49e7eafc6b41b701dcd8737db2488c` |
| `task_tower/__main__.py` | `b233be3d4570816c4178d8e3a21af0cea6ac772fb2927eeb8c549a3844f75cdb` |
| `task_tower/books.py` | `d838086f3a340a657b2635f2f559296945f5b2a4b4ece3ece0e82a0c55e30e87` |
| `task_tower/capture.py` | `aecb96e7ae4e9bd8fafbcd85f44ae548a183a4a6ef3a22192247321a93f3f331` |
| `task_tower/capture_cli.py` | `ea41cf183930a513eba501652b2ba80d89b118f58be6eea67c5f5c1f37c19c8e` |
| `task_tower/capture_migration.py` | `d8c5c26d6e7ca8b6be77d1543cd679d8bb38d1440563753f8669a766753c09b7` |
| `task_tower/creation_journal.py` | `c5c6be3332276d038d151d99d101893e00bf1a6638af7a1b64be336d340412e3` |
| `task_tower/dispatcher.py` | `b070801cf3085362b730b0adc8028ea91b2d56951be9398037ba3e017d9790e4` |
| `task_tower/github_tasks.py` | `7a59f38382fb9676536c1307fc863edca331be93cdd2858d3ebcfe8a85911519` |
| `tests/test_capture.py` | `92997f5da84d2fc8ed0078fdbc119b852fb94a74e5b77820b28bf0cf660af830` |
| `tests/test_capture_cli.py` | `8f87bb0cff1bee4a1ca041141e557bdf54cfa50fb113f727c39e45b06298fec8` |
| `tests/test_capture_migration.py` | `60fbd21c816b35402dab3f62d07553a6cb2c68759f61f9c23588d6b23aa289b3` |
| `tests/test_dispatcher.py` | `041a03f10bd61f5a0a1204875f08c890ef83d2041cfd1261ec82efe562808c6d` |

## Same-Issue22 merge-identity recovery documentation (CURRENT)

Verdict: ACCEPTED for the bounded documentation follow-up and current 22-input development manifest below. No production changes or unresolved documentation blockers. Earlier exact-source findings/acceptance remain historical. Existing accepted coordinator scope includes process and session-capture documentation; no capture specification/plan contract or API change is introduced.

Reviewed the entire two-file diff against main cd0927810683edfbc93caf6b6d4db67338aba6f8. It requires the exact standalone Task-Tower marker to match private task/Issue mapping before merge and records that binding with head/base acceptance. Genuine PR37 event remains unbound with task_ids=[]; green CI cannot imply task acceptance or completion. The runbook preserves the original artifact/refusal history and forbids synthesized bundles, forged receipts, journal reset or manual closure. A correctly marked bounded reviewed follow-up continues the same open Issue22 and keeps its slot occupied. Unrelated merges remain blocked until the recovery commit independently passes exact-main acceptance/publication and automatic closure; development may continue independently. This is a repair of the unfinished current integration cycle, not permission to skip it or start a replacement task.

Independent baseline evidence: Git diff between accepted PR37 head 4cb5ec79003ff92965ce71d9d9fb518ec3cb4c8f and merge cd0927810683edfbc93caf6b6d4db67338aba6f8 is empty. GitHub run 41336591697 attempt2 is completed/success on all three platforms; logs explicitly check out cd092781 and run 348 tests per platform. The genuine downloaded Linux artifact identifies cd092781, passed checks and empty task_ids. See private runtime/pr-acceptance/main-37-recovery-barrier.md for the strictly scoped independent source/CI baseline verdict. No synthetic task-bound postmerge acceptance is created. No new test run was needed for this documentation-only diff; fresh git diff --check exited0.

Current sourceHash: `70f5904fd44d9ee42b02af5bfdef5c735351b40dcc9b7b8c9f1823ff4596d915`. Same canonical UTF-8/LF algorithm; evidence/cards/runtime state excluded.

| CURRENT stable input | Canonical SHA-256 |
|---|---|
| `AGENTS.md` | `29c2d287fff80873a6b034f1c7cd8f8259b85b744e45a2cf62ae193dae7f4311` |
| `README.md` | `eb42ec82b900bc80e67e8b5234002d664cbc21e52325a6e2a3f3f1799ec688e2` |
| `docs/development-process.md` | `c0a5cdb73ceb45b855064e408e9f2ecb55ff520b76cd83b079cd05a3a54a09c9` |
| `docs/dispatcher.md` | `82076f3284e8c4b380a6d32a0b4efc21b5ae8dafb68dae73da857b18d583de00` |
| `docs/github-books.md` | `0da864ae878de40cb5066a505b675a9a636a8d042f71d7f7ff268adc9dab4171` |
| `docs/roadmap.md` | `8448c15f88a2997d068a24282853271084bd8d7fdb2cde3fcede641d1aa12974` |
| `docs/session-capture.md` | `dea1a154d545ef99f7c393d27d1be8e5d5c7ed26e69044e5303c4788ee73c822` |
| `docs/superpowers/plans/2026-11-01-session-capture.md` | `52e8a0263b5755cc3acdb36c9824fb74de34e736d7055593262c26502e9ae746` |
| `docs/superpowers/specs/2026-11-01-agent-development-architecture-design.md` | `dc8de3c2d0b8b8551498b3c652f89e4ee32cd903cb7bf5c8c5ce3832199833ac` |
| `docs/superpowers/specs/2026-11-01-session-capture-design.md` | `bf601bcd82206b61c85f735be88d87d3ec49e7eafc6b41b701dcd8737db2488c` |
| `task_tower/__main__.py` | `b233be3d4570816c4178d8e3a21af0cea6ac772fb2927eeb8c549a3844f75cdb` |
| `task_tower/books.py` | `d838086f3a340a657b2635f2f559296945f5b2a4b4ece3ece0e82a0c55e30e87` |
| `task_tower/capture.py` | `aecb96e7ae4e9bd8fafbcd85f44ae548a183a4a6ef3a22192247321a93f3f331` |
| `task_tower/capture_cli.py` | `ea41cf183930a513eba501652b2ba80d89b118f58be6eea67c5f5c1f37c19c8e` |
| `task_tower/capture_migration.py` | `d8c5c26d6e7ca8b6be77d1543cd679d8bb38d1440563753f8669a766753c09b7` |
| `task_tower/creation_journal.py` | `c5c6be3332276d038d151d99d101893e00bf1a6638af7a1b64be336d340412e3` |
| `task_tower/dispatcher.py` | `b070801cf3085362b730b0adc8028ea91b2d56951be9398037ba3e017d9790e4` |
| `task_tower/github_tasks.py` | `7a59f38382fb9676536c1307fc863edca331be93cdd2858d3ebcfe8a85911519` |
| `tests/test_capture.py` | `92997f5da84d2fc8ed0078fdbc119b852fb94a74e5b77820b28bf0cf660af830` |
| `tests/test_capture_cli.py` | `8f87bb0cff1bee4a1ca041141e557bdf54cfa50fb113f727c39e45b06298fec8` |
| `tests/test_capture_migration.py` | `60fbd21c816b35402dab3f62d07553a6cb2c68759f61f9c23588d6b23aa289b3` |
| `tests/test_dispatcher.py` | `041a03f10bd61f5a0a1204875f08c890ef83d2041cfd1261ec82efe562808c6d` |
