# TT-CAPTURE-001 independent specification and plan acceptance

Verdict: ACCEPTED for implementation against the exact canonical inputs below.
Reviewer: independent `/root/capture_spec_acceptance` instance; not the implementer.
Date: 2026-11-01. Worktree: `task-tower-capture`; branch: `feat/session-capture`.
Base inspected: `9ba02c2f207c4f2664331774ad39314ab0d51b3e`.

This accepts the specification/plan stage only. It does not accept production code, tests, PR/head/base, main, Issue closure or unattended operation. Any change to accepted spec/plan inputs invalidates this verdict until independently reviewed.

## Findings resolved in the reviewed sources

1. Existing metadata parsing counts literal comment markers even inside JSON and Markdown fences. The spec and test plan now require a versioned marker-inert typed encoding for lossless provenance, escaped human display and malicious-marker tests across original text/session fields. Decoding never grants lifecycle, queue or execution authority.
2. Existing `import_card(path)` reads its input again. The plan now imports a private immutable snapshot of validated bounded bytes, retains original source identity, and rechecks original identity/hash before import and registry publication. Source drift after creation leaves a recoverable canonical Issue, never a second POST or a rewritten active card.
3. Promotion now requires cross-process local serialization and drift tests, and explicitly distinguishes supported conditional mutation from a non-atomic final-read/PATCH. Cross-host/manual editing requires serialization if no server precondition exists; no atomic remote guarantee is claimed.

## Acceptance assessment

Stable repository/provider/event identity and payload binding are explicit; independent events with equal text remain distinct. Project-first preflight and durable CreationJournal reservation precede POST; unknown outcomes never blindly resubmit. Same-Issue promotion retains source identity and cannot authorize execution. Parent/sub-issue and milestone data are separate, repository-qualified, and rendering remains Issue #23. Legacy bytes, evidence, loader/publisher and historical snapshot hashes remain compatible; GitHub is canonical editable truth and private migration registry is provenance only. Alias, replacement, cross-process registry/CAS, drift, bounded payload and secret-safe diagnostics have explicit negative tests. No new frontend, ambient/all-chat collection, Codex database access or credential grants are in scope.

The two-Issue worktree policy and independent stages are preserved. Main integration remains serialized and requires fresh whole-diff head/base acceptance, exact-main checks, independent postmerge acceptance and automatic closure verification. Coordinator-owned process context was read only, not copied or modified.

## Verification and stable input manifest

Reviewed full specification/plan and the existing parser/import/journal interfaces. `git diff --check` exited 0 (new untracked documents were additionally decoded as UTF-8 and normalized on write). Production tests were not run: this is a document-only pre-implementation gate. No production edits, commits, remotes or child agents were used.

SHA-256 normalization: decode UTF-8 (optional BOM), normalize CRLF/CR to LF, encode UTF-8 without BOM; retain final-newline state. This manifest excludes mutable TaskCards, runtime/private state and evidence itself. Parent/process references are context inputs and are not copied into this branch.

| Stable input | Canonical SHA-256 |
|---|---|
| `docs/superpowers/specs/2026-11-01-session-capture-design.md` | `fee62c2da3faee0359daf8ccfb07539251df30e1afe78b5bec9e1a625ce096ba` |
| `docs/superpowers/plans/2026-11-01-session-capture.md` | `047a5d85d56a7adca4af22280e28910d5a90226978516616c36c35443662f7a6` |
| `AGENTS.md` | `5dca4fae766f6c995ef9769b296c2bbdf719e8af8ee60413c6d09024a0f11c7a` |
| `../AGENTS.md` | `7a47ea26e54a2fc5d011b12611e639aaf97c28780b4878b4cd2aeebe767a1455` |
| `../task-tower-github/docs/development-process.md` | `d13da41354b40b706d14cdc44c57569c8914500e5f8ba870c7aeadaac3c2bcf0` |
| `task_tower/github_tasks.py` | `71a44ab56f186468431d5b26919f01d7be96321fe4ce1e49249a37a1a7732c6a` |
| `task_tower/creation_journal.py` | `b2fc2f68151f2d63415a727914fe17ec123d4ad64f428eb62274576db1975f51` |
| `task_tower/project_connections.py` | `60a300b4275910cf0eee38dfade879d6a9596a36bdd3001928cd8e0d5f55c250` |
| `task_tower/github_publication.py` | `1bc796004a6d323c32d928c71de52c9730c5863d22e86606f53276cb2da7c92c` |
| `task_tower/project_worker.py` | `9cb0002ccf5959220b8a7c20b8f656e3f4983319ff0e4805408d44be6fe0b2cc` |

## Coordinator integration scope refresh (2026-11-01)

Verdict: ACCEPTED for the amended specification/plan and bounded integration scope. The earlier review and manifest above are retained as historical pre-implementation evidence; the following manifest supersedes its spec/plan bindings for the current scope. This reviewer inspected the two-line `_source` authentication forwarding diff and its single regression test, plus the published process document. The narrow existing-authentication backport and coordinator documentation reconciliation are permitted by the addendum; no executor, new credential scope, relaxed verifier or capture API change is authorized. The external process reference was not modified by this reviewer. Only the two specification/plan files and this evidence were edited in this refresh.

This is specification/scope acceptance only: final whole-diff development/testing, PR head/base and exact-main acceptance remain independent gates. Test results reported by the coordinator are not re-attested here. Mutable TaskCards/evidence/private runtime state remain excluded. Canonical hashing uses the normalization stated above.

| Current stable scope input | Canonical SHA-256 |
|---|---|
| `docs/superpowers/specs/2026-11-01-session-capture-design.md` | `bf601bcd82206b61c85f735be88d87d3ec49e7eafc6b41b701dcd8737db2488c` |
| `docs/superpowers/plans/2026-11-01-session-capture.md` | `52e8a0263b5755cc3acdb36c9824fb74de34e736d7055593262c26502e9ae746` |
| `README.md` | `ff8e4ca904cfb435e180cbaea0e497d4139ebfbce6603a783d9fb8e656babd87` |
| `AGENTS.md` | `c331c6881d9e792f7839b620475ff71c051edc92066f688e6d6da109a57dfea8` |
| `docs/roadmap.md` | `8448c15f88a2997d068a24282853271084bd8d7fdb2cde3fcede641d1aa12974` |
| `docs/dispatcher.md` | `86e905b6e7954133855ffbeaf40acd719416ba9640752aacefe43ec0087316b5` |
| `docs/github-books.md` | `0da864ae878de40cb5066a505b675a9a636a8d042f71d7f7ff268adc9dab4171` |
| `docs/session-capture.md` | `af6683473d4e14485a42c7dbfa2af3dba69aee56b221fb87b12203d9156b97bc` |
| `docs/development-process.md` | `d13da41354b40b706d14cdc44c57569c8914500e5f8ba870c7aeadaac3c2bcf0` |
| `task_tower/dispatcher.py` | `b070801cf3085362b730b0adc8028ea91b2d56951be9398037ba3e017d9790e4` |
| `tests/test_dispatcher.py` | `041a03f10bd61f5a0a1204875f08c890ef83d2041cfd1261ec82efe562808c6d` |
| `../AGENTS.md` | `7a47ea26e54a2fc5d011b12611e639aaf97c28780b4878b4cd2aeebe767a1455` |
