# Independent Issue21 qualification-wire specification review

Reviewer: /root/fetch_timeout_diagnosis

Verdict: ACCEPT the dated Concrete wire clarification and corresponding Task1 plan instruction for the exact document bytes below. No blocking representation/safety ambiguity remains for implementing this policy/discovery grammar. This is specification acceptance only: it does not provision an installed policy, qualify the native CLI, approve the partial implementation, or grant native probe/run authority.

## Bound inputs

| Document | Raw SHA256 | Canonical UTF-8/LF SHA256 |
| --- | --- | --- |
| task-tower-opencode/docs/superpowers/specs/2026-11-02-opencode-adapter-design.md | 2247ccb302b7e40069bba2bd6e098e15831bf018592f1bf875f2484af58d64c2 | fb87a0392480736769e60780f378df77c570ab5d1f4339d70df3ee519542466d |
| task-tower-opencode/docs/superpowers/plans/2026-11-02-opencode-adapter.md | d44001d2fa5aa7cdcabe9f4e84ef4b0497d51b81b20ea04e8cbf929572d7ce66 | d7d5e6c3426773dd4829570c9aeb962a45c0c08f28930bbbcca8f2e6cc81d28f |

Historical accepted-main binding review: runtime/accepted-main-downstream-binding-review.md, raw SHA256 3b2026a575c8b52a01a3207efa16a8ff9ee48fbe0fc6ed854af1400f572a9db6. Retain it as a prior exact-input verdict rather than claiming it reviewed the new wire.

Public primary-source cache: runtime/opencode21-task1-source-manifest.json, raw SHA256 064f3dc42c0c44e3a828ddbd7f1bd694d05e60d6dc2700a12cd1c807766f694d. Independently verified all19 cached file hashes against the manifest at revision9bbb8ce18c80f099e0e448775f59d965ead40a21. These are public source files, not local user native state. Transitive startup-source closure remains incomplete and no native qualification is inferred from this manifest.

## Change isolation and source findings

Inspected the exact Git diff. Only one new dated wire section is inserted in the design and one associated instruction paragraph in the plan. Removing those additions in memory exactly reconstructs the committed prior canonical documents, including R3/R4 requirements and actualM binding. The unchanged prior design canonical hash is3c7987e1972b28026ec8a6d5768e934baaa823c1ff6493169c92e276e75fe018; prior amended-plan canonical hash is997e940b5100781053a7e8112915ce02576dc929ce29625b7aa5c4200a7a9419. No legacy six-role support, new public journal reason, scope key, installation/model/auth action or POSIX capability is silently added.

Read the cached primary global-roots/global, CLI config/migration/startup and credential-dependent config sources. Tagged global roots derive from XDG/home/tmp selectors; global acquisition recursively creates data/config/state/log/bin/repos/tmp directories. CLI config includes cli.json; migration includes tui.json and state/kv.json. Startup invokes ensurePluginRuntime before askpass/version dispatch. Config depends on Credential and WellKnown services. The new mandatory startup-root/config/metadata entries and conservative unsupported conditions address actual source surfaces missed by a project-opencode.json-only inventory. They do not assert that these19 files close all transitive startup effects.

## Authority and type assessment

The exact six qualification keys and three closed {path,sha256} artifact references are sufficiently defined for strict parsing. Referenced files remain private, bounded1MiB, strict UTF-8, regular single-link and outside all checkout/run roots; the bytes whose digest is checked are the bytes safely read/used. Alias/reparse/identity changes, extra keys, digest mismatch, oversized data and nested-reference indirection must fail closed. source_audit_sha256 is explicitly equal to qualification.source_audit.sha256; surface identity is fixed. Artifact prose is not executable policy or a proof interpreter.

The trust root remains the installation's genuinely independently accepted evidence installed by the trusted coordinator and pinned by the existing private profile fingerprint/policy_evidence_sha256. The implementer, task text, fixture, reviewer_id field and an approve string cannot establish that provisioning. Runtime verifies installed pins and fresh host observations; it must not substitute a newly invented self-attestation field or parse arbitrary report prose into authority. The new booleans are exact permission bits only. False blocks the corresponding operation before a child; native-run permission cannot bypass probe permission, actual successful version qualification, native_launch_authorized or other preflight gates. Registering valid bytes cannot set probed/verified/events/resume. Probe and native execution callers must enforce their corresponding permission and evidence gates; a generic positive discovery comparison is never a native-run capability.

Missing-parent representation is closed and reconstructible: nearest existing directory parent, actual identity and ordered safe missing components must reconstruct exactly one candidate path. The directory-kind constraint follows its required parent role; an existing file cannot serve as a parent. Dot/dotdot, separators, ambiguous normalization/parents and reparse traversal are rejected. Canonical decimal device/file_id strings bounded to unsigned128-bit values avoid JSON integer loss and accommodate actual filesystem IDs. They must come from positively available actual platform identity calls; a caller/default/unsupported identity does not qualify. Windows case/normalization and membership rules in the original spec remain binding.

Derived startup roots use the pinned algorithm and existing seven scope selectors; no guessed AppData root or extra scope authority is introduced. Absent roots that startup would create return unsupported_startup_directory_creation without creating directories. Credential/account/session/database contents remain unread: metadata-only presence or unresolved credential-dependent influence returns unsupported_credential_dependent_discovery. Parent identity/membership can expose presence without hashing the forbidden file. Partial unsupported diagnostics cannot masquerade as a complete accepted inventory or allowed preflight. No attempt to force qualification by creating empty config, reading native KV/DB, changing roots or stripping user settings is allowed.

Direct/internal unsupported_kind rejection is deliberately distinct from unchanged bounded public policy-revoked/environment-unavailable/invalid-policy projection. The plan adds corresponding exact-key/permission/reference/parent/identity/root/credential-influence fixtures and zero-child checks, not a new journal reason enum.

## Required implementation and subsequent acceptance boundaries

The narrow closed-kind guard checkpoint is not reviewed or accepted by this specification verdict. Preserve its frozen bytes/history while implementing only the newly accepted Task1 grammar/collector work through fresh RED/GREEN and distinct development/test review. Before common-loader expansion, preserve independent generic/role/pipeline closure and unchanged Codex/custom schema, argv, fingerprints and capability shapes. Otherwise registry expansion would restore the known fallback path.

Tests must include missing/false operation permissions, true native_run without native_probe, actual-version evidence absence, malformed/extra keys, reference identity/hash drift, alias/reparse/hardlink boundaries,128-bit limits/noncanonical decimal strings, invalid parent-file/dotdot/separator chains, changed membership, absent startup roots, and metadata-only credential presence without forbidden file reads. Synthetic accepted reports/test fixtures can validate protocol behavior but must never be installed as actual native authority or presented as source/installation qualification.

Native CLI remains unqualified. Complete tagged transitive startup closure, a distinct installation qualifier, coordinator-pinned real host evidence, actual permitted version qualification and later task/reviewer/native containment evidence are separate requirements. No install, auth change, model selection, native state inspection, POSIX58-62 execution or deferred Claude20 work is authorized. Preserve the original Issue21 delivery and unknown/replay fences.

Root should save a new content-bound spec-stage receipt for these two input hashes, retaining all prior binding and wire-finding history. Later code or document changes invalidate this exact-input verdict. Only this report was written during review; no code/Git/runtime/native/auth/probe mutation occurred.
