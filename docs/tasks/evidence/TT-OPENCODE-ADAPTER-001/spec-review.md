# Independent OpenCode specification / plan review — round 1

Reviewer: independent read-only spec acceptor `/root/opencode_spec_acceptance`, 2026-11-02.
Verdict: **REJECT — revise before implementation**. This is Source/Spec-stage review only; no product code, native CLI, installation, full test suite, Git mutation or publishing was performed.

Reviewed accepted-base contract: `56f8ab12f21ab91030ffe54de96520fcd979dc04` (#15). No candidate #20 observer API or unaccepted #16 API is assumed. Read repository AGENTS, Superpowers brainstorming builder-check instructions, entire design/plan/research/card, and actual profiles/harness/worker/process/Windows Job code. Parent-provided Issue21 admission identity is treated as coordinator provenance, not native proof. This review does not independently attest the live GitHub Issue body or delivery receipt.

Content binding (SHA-256):

- design: `c3f2d947739a341c0cd4a53f460a45e56f69062f8d803dfa830635c07181a60a`
- plan: `4a7a32090684fb8f6149d29cf1f8c13c13b2a7b18d7d120699250e841073a833`
- research: `1dfba8f8311a239ef6dfba8afb2df3475834d37bf6f7828b09bc9a91c9bacf63`
- pending task card: `a89fe2845756f1cad0c715aa74120f2c9cd0a0b7cfe4c56c8ab022eeeef3116c`

## Blocking findings

### P1 — The precise policy schema cannot bind complete discovery or inherited overrides

Anchors: design lines 29–38; plan Task 1 lines 44–49.

The design promises to fence config/discovery drift and qualify all inherited config/permission/server/instrumentation/askpass overrides, but the strict evidence inventory permits only existing `{path,role,sha256}` file entries. Its canonical digest only covers that list. There is no representation for approved absence, discovery root/directory membership, ancestor locations for the newly created worktree, or the private environment snapshot/approved override presence and value binding. Rehashing every declared file therefore cannot detect a new eligible config/local plugin/agent file, or a changed OPENCODE config/askpass override. All declared hashes and assertions may remain unchanged while startup execution/install/model policy changes. A blanket “unknown discovery blocks” rule has no concrete detection mechanism under the specified schema and ban on broad home searches.

Tagged V2 confirms missing eligible sources matter: [discovery.ts](https://raw.githubusercontent.com/anomalyco/opencode/v2.2.5/packages/core/src/config/discovery.ts#L12-L23) models eligible sources including paths that may appear later; [ancestor/global discovery](https://raw.githubusercontent.com/anomalyco/opencode/v2.2.5/packages/core/src/config/discovery.ts#L52-L134) includes multiple compatibility directories. [CLI startup](https://raw.githubusercontent.com/anomalyco/opencode/v2.2.5/packages/cli/src/index.ts#L32-L35) handles an inherited askpass override before ordinary command dispatch. Thus this matters even before the version probe.

Required revision: define a bounded, noncredential discovery manifest and verification algorithm covering approved roots, explicit missing candidates, relevant directory membership and the actual launch worktree/ancestors; define which inherited policy-affecting names are rejected or privately bound to the reviewed policy, including absence/change. Verification must happen before probe and immediately before launch without reading auth or resolving secret substitutions. Clarify evidence-file authority/immutability binding so the reviewed policy is the one consumed. Add fault tests for a newly created eligible file, changed membership, new ancestor source, and added/changed policy-affecting override; each must prove runner not called. An unknown surface should remain a concrete external qualification blocker. These are builder-owned choices within the established no-install/preserved-model scope.

### P2 — Frozen stdin verification has no expected identity at the opening boundary

Anchors: design lines 46–50; plan Task 2 lines 56–58 and Task 3 line 68.

Task 3 returns input path/hash/bytes, and Task 2 requires mismatched frozen input to be rejected before child creation. However, the runner receives only `stdin_path`; no expected digest/length or already-validated handle is passed. Safely opening a current regular single-link file and checking its size cannot establish that those bytes match the frozen launch identity. A worker hash check followed by a separate runner open leaves replacement/in-place mutation between those operations unbound; an open handle alone also does not freeze POSIX file contents.

Required revision: specify the additive expected identity/transport contract and ensure the exact bytes made available to the child match it before child creation (for example, bounded verified private staging to an owned immutable transport, with expected SHA/length passed to the runner). Define ownership/close behavior and no-child mismatch state; keep legacy calls/result shapes unchanged. Add a deterministic replacement/mutation fault test between producer verification and runner consumption, in addition to the current static size/link tests. Do not claim that a pathname or ordinary open handle is immutable content.

## Nonblocking assessment

The fixed V2 standalone choice, cwd plus PWD, complete postcapture parsing, explicit EOF/truncation rejection, full60 transport budget, strict separate local result, native-versus-fixture distinction and deferred resume are coherent with the accepted executor architecture. Source spot checks support standalone's generated credential and stdin lease [standalone.ts](https://raw.githubusercontent.com/anomalyco/opencode/v2.2.5/packages/cli/src/services/standalone.ts#L14-L50), PWD selection and stdin [run.ts](https://raw.githubusercontent.com/anomalyco/opencode/v2.2.5/packages/cli/src/run/run.ts#L67-L75), and emitted partID / projection completion shapes [noninteractive.ts](https://raw.githubusercontent.com/anomalyco/opencode/v2.2.5/packages/cli/src/run/noninteractive.ts#L390-L414). This is source validation, not installed artifact/native qualification.

Native absence and startup authorization remain external qualification gates; implementation acceptance cannot close Issue21. Whole-diff exact head/base acceptance, serialized merge, exact-main independent acceptance and automatic closure remain pending. Preserve this initial rejected report and append subsequent independently content-bound rounds.

---

# Independent specification / plan review — round 2

Reviewer: `/root/opencode_spec_acceptance`, 2026-11-02. Verdict: **ACCEPT for Source/Spec and implementation-plan stage only**. No important unanswered builder question remains within the stated scope. This does not accept implementation, installation policy provisioning, a native probe/run, event capability, tests, PR/main integration, or Issue completion.

Re-read the entire current design, plan, research and pending task card against the previously inspected accepted #15 executor API base `56f8ab12f21ab91030ffe54de96520fcd979dc04`, R1 findings, applicable AGENTS and Superpowers builder-check criteria. No sibling #20 API or unaccepted #16 behavior is assumed. Prior tagged primary-source spot checks in R1 remain applicable to the same pinned V2 source; this is not new native evidence.

Accepted content SHA-256 bindings:

- design: `99a834e01a851eb5351c55e3e9697758a0fb9e715d4bad564d66e73041a7c3a8`
- plan: `8868bfc4c2c26670783e73eb854bcb1507c9fbf623f11d15bb284e686e7337ef`
- research: `117bb639abcbcbdeead211481b45d8982729abca8e0af0a35dd9739170f18e93`
- still-pending task card: `a89fe2845756f1cad0c715aa74120f2c9cd0a0b7cfe4c56c8ab022eeeef3116c`
- report bytes observed before this append: `a2b1f8dce04f38dc28c4f7e7175d0b34850acae1b3c27d63201e021eff4cccc8` (preserved byte-for-byte).

R1 P1 is resolved at design level by explicit missing/file/directory inventory forms, safe identities, direct membership, finite eligible traversal and bounded failure, actual future worktree/ancestor expansion, source-template binding, opaque private policy-environment presence/value hashes, preprobe rejection of askpass/injection/unknown selectors, and independently reviewed profile-pinned evidence bytes. Fresh real collection/comparison before each native child is a concrete mechanism; booleans or an accepting callback cannot substitute. Unsupported compatibility/plugin/MCP/managed/credential-dependent surfaces remain blocked without reading auth or changing user configuration. The source table, collector and qualification artifacts are future implementation deliverables requiring independent task review, not already accepted discovery coverage or native authority.

R1 P2 is resolved at design level by the additive stdin_spec expected digest/size/filesystem identity, bounded prelaunch verified copying, before/after source identity checks and private anonymous staging with only a read handle inherited. Deterministic producer/open/read/stage/spawn fault cases cover mutation and replacement. Legacy None/DEVNULL/result behavior remains explicit. Task review must inspect the actual OS handle permissions, inheritance and cleanup; an O_RDWR descriptor merely described as a read handle would not satisfy this specification.

The complete plan preserves exact fixed standalone invocation/cwd/PWD, full60 unchanged pins, bounded full capture and EOF validation, conservative event/result conjunction, timeout/cancel precedence, unknown ownership fencing, no replay/attach, distinct native implementation/reviewer identities and common custom contract. Source-defined discovery closure and no-install startup proof are mandatory before even --version. No install/update/auth/model-selection permission is created. The current lack of a qualified native executable/policy remains an external release blocker; fixture success cannot close it.

Implementation remains subject to the explicit accepted-current-main re-audit before Task 1. Main changes that alter these interfaces require updated independently reviewed plan bindings. This adapter specification introduces no global fixed-two scheduling limit; existing legacy API compatibility does not establish a new runtime capacity policy. Exact head/base whole-diff acceptance, current three-platform CI, serialized merge, exact-main independent postmerge acceptance and automatic Issue21 closure remain separate gates.

No product code, card status, shared documentation, tests, native CLI, installation or Git state was changed in this review. Only this evidence appendix was written.
---

# Independent specification / plan review — round 3

Reviewer: `/root/opencode_spec_acceptance`, 2026-11-02. Verdict: **ACCEPT for the R3 Source/Spec and implementation-plan description only**. R2 ACCEPT remains historical acceptance of its exact content; this appendix does not retroactively change that verdict. No important unanswered builder question remains after the new dispatch boundary is included. Implementation is still blocked on the explicitly required fully accepted-current-main API re-audit and concrete interface/test mapping.

Read the entire current design/plan/research and pending card, retaining the R1/R2 context. Independently inspected the accepted-base generic builder and, strictly as provisional source data, current #16 candidate executor_harness.py, pipeline_policy.py, pipeline_roles.py, pipeline.py, pipeline_worker.py launch references and shared process runner in task-tower-github. Candidate source was read, never imported/executed or adopted as an accepted API. The candidate mapping is consistent with the reported gap: generic noncustom fallback, role builder delegation/fallback, common profiles copied into pipeline policy without a kind matrix, and pipeline role launch through build_role_invocation. This inspection does not attest that candidate HEAD, working changes, tests, native trial, main or closure passed acceptance.

Accepted SHA-256 content bindings (raw bytes and canonical bytes are identical for these four files):

- design: `753dab7fde362b0bcaba7a47dc33ca3861059639fe277fa2dd3a979c6141c142`
- plan: `2358b16278910a9c3adc45fa636c4367f9ffe68be398cf561b8f1059d2c1ece4`
- research: `103a9f685df9692a860b29ddb456a9d63c41c6e1d7677a871d598c3910929d34`
- still-pending task card: `a89fe2845756f1cad0c715aa74120f2c9cd0a0b7cfe4c56c8ab022eeeef3116c`

Preappend report binding: raw `b910a9b352f48370af2e4d8e069e578a01d32d484a74c43d1003888f796072ea`; canonical `1e012e8055fbc278f0e64d0bc48067bb17e9b50f472a807f1c676364aaef4085`. Canonical means replace CRLF bytes with LF only, retaining the UTF-8 BOM and all other bytes; it does not strip BOM, normalize lone CR, trim whitespace or add a newline. The full raw preappend prefix is preserved.

The R3 correction covers registration versus consumer launch authority at both direct-builder and installed-policy boundaries. Generic and role builders have explicit codex/custom dispatch; OpenCode, missing, malformed and unknown kinds fail closed. Pipeline policy must reject OpenCode before stage preparation/probe/native launch, independently of common profile registration and independent of any foreground native success. Actual pipeline admission/worker tests and direct role-builder tests are required for all six roles, with no executable/probe/runner effect and no manufactured result. The foreground worker has an exclusive OpenCode branch using fresh policy preflight, fixed V2 argv, verified staged stdin and native events plus existing strict result validation. Existing Codex/custom behavior is explicitly preserved. Closing every consumer before widening the loader is a coherent implementation order.

The provisional candidate currently has one executor profile per task, not six independently configured role-profile fields. The plan's accepted-main re-audit and actual-entrypoint tests govern how the six role cases are exercised; this wording does not authorize inventing a new role-assignment schema. Inspect actual run_role/authority preparation ordering when implementing, so direct call and persisted/reloaded pipeline paths meet the specified early rejection rather than relying solely on a late generic-builder error. These are implementation review checks within the accepted requirement, not additional native authority.

R1 discovery/environment/evidence and frozen stdin corrections remain intact. Finite tagged-source table coverage, no-install startup proof, real host closure, private pinned policy, no auth/session/credential reads, exact source/PWD, real read-only staging handles, EOF/truncation/event bounds, conservative cancel/cleanup/reconciliation, preserved model and no implicit replay remain mandatory. This review accepts a plan to implement and independently qualify those mechanisms; it does not assert they already work.

No global fixed-two coordination policy is introduced. Existing shipped numeric runtime bounds remain distinct from later #18 capacity work. Re-read fully accepted main after #16 exact-main CI/independent postmerge acceptance/automatic closure, record actual signatures and test modules, and obtain any affected updated plan acceptance before code. Native availability/policy qualification, distinct native task/reviewer/cancel proof, complete suite and three-platform CI, exact-head/base whole-diff PR acceptance and serialized exact-main acceptance/closure remain outstanding gates. No product code, card, shared docs, Git state, native CLI or installation was changed; no product test was run. Only this report appendix was written.

---

# Independent Windows release scope SPEC/PLAN review

Date: 2026-11-02. Reviewer: windows_scope_spec_acceptance (fresh instance, distinct from amendment author). Scope: the six-file Windows release amendment only; this does not re-approve unrelated historical specification content or implementation. No tests, native/model execution, installations, authentication changes, product/card/documentation writes or GitHub mutations were performed.

## Verdict

Issue #16: ACCEPT amendment for the exact two hashes below. Windows-only native pipeline execution, early work/watch/_action/_dispatch rejection before _runtime/journal initialization, direct-entry defense, portable admission/lookup/status/cancel/inspect and mandatory Windows containment/shutdown/physical-DB identity/recovery gates are coherent. No permission to ship saved POSIX scope/bootstrap WIP is given.

Issue #18: ACCEPT amendment for the exact two hashes below. Pure group policy/DAG/provenance remains portable; Windows resource admission and conditional real >=3 concurrency proof remain mandatory. Neither fallback resources nor pure Task1R acceptance enables unsupported native execution. The actual accepted #16 main/API/CI/postmerge/automatic-closure gate remains intact; this verdict does not open runtime integration now.

Issue #21: ACCEPT amendment for the exact two hashes below. Windows native OpenCode/custom qualification and new stdin/containment are separated from portable policy/parser/provenance/closed dispatch. Existing Codex/custom behavior is explicitly preserved. Exact accepted #16 main API re-audit remains required before Task1; this verdict does not authorize coding before that gate or native probes without installation-owned qualification.

No blocking amendment findings. The explicit dated precedence at line 5 in each file governs retained earlier native POSIX promises. Three-platform CI requirements remain requirements, not contradictions: they cover portable regressions and Windows native proof with explicit per-test classification. Historical POSIX-native Task3B and transport requirements are deferred by that precedence; they cannot be claimed accepted merely by running synthetic fixtures.

## Review evidence and implementation constraints

Compared every actual amendment against its preserved pre-amendment bytes with git diff --no-index. Independently recomputed all six current SHA256 hashes and all six prior SHA256 hashes; every value matches runtime/windows-scope-spec-manifest.json. Read repository instructions and inspected surrounding platform, native-evidence, dependency, legacy-interface and completion clauses. Diff contains the new normative sections, portability wording changes and explicit #61 collector deferral, not rewritten historical reviews.

The amendment is honest about saved commit 18e9a3985ad3b86a02d58703ef8e8a2afdd9a0e2: unaccepted WIP/manual diagnostics, no runtime authority. Feature #58 and children #59-62 are named deferred work. Their live GitHub milestone/admission state and remote-branch contents were supplied by coordinator and were not independently queried in this local content review; operational verification remains coordinator responsibility.

Required implementation review checks (already implied by the accepted text, not additional scope):

- Record per-test classification before changing mixed modules. Keep all applicable portable regressions in Ubuntu/macOS/Windows CI and Windows-native tests on Windows. Retained native POSIX checklist entries in #18 Task3B and #21 Task2 must be marked deferred to #61/#62 in execution evidence, never silently marked PASS or used to delete an entire mixed module.
- Prove unsupported-platform rejection at public and direct effect-producing paths, before helpers, checks, worktrees or publication. For #16 specifically prove no _runtime/journal side effect. Do not simulate a supported native OS as platform qualification.
- Keep resource fallback subordinate to platform capability; verify Windows physical SQLite pin and ordinary/hot recovery fixes independently. Windows-only scope does not excuse known Windows defects or shared shutdown-budget failures.
- Interpret #21 direct adapter/probe restriction as the new native OpenCode execution surface; preserve the established queue/protocol and existing Codex/custom surfaces. New stdin_spec native transport is Windows-only until #62 qualification; default None/DEVNULL legacy calls remain unchanged.
- Retain head/base-bound independent PR acceptance, successful current CI, serialized merge barrier and exact-main independent postmerge/automatic verified closure. This review is SPEC/PLAN scope acceptance only, not any of those later stage verdicts or a night-readiness claim.

## Exact reviewed raw SHA256

| File | SHA256 |
| --- | --- |
| task-tower-github/docs/superpowers/specs/2026-11-01-stage-pipeline-design.md | `5524d16570530662e25006e91e4159afecbecd103f327d1c1b9b48fc3d3fc6f5` |
| task-tower-github/docs/superpowers/plans/2026-11-01-stage-pipeline.md | `d48b782e476349103455996bebb9144149326842c59b7ff1959a8390c1a05ee3` |
| task-tower-capture/docs/superpowers/specs/2026-11-02-agent-groups-design.md | `c488845f3fcd2cf446f820452c7c2dd1b22d2cae6fbd257bb3813e7b8aeae867` |
| task-tower-capture/docs/superpowers/plans/2026-11-02-agent-groups.md | `cf8e7a6946c5a1c5fcf0869ed9b9a7f211212c62fd63d0422782638d7a28530a` |
| task-tower-opencode/docs/superpowers/specs/2026-11-02-opencode-adapter-design.md | `aafe165c23182656f85fe272b8fa2ee0fd03a73627fb7e515bf6fa18cf93c03b` |
| task-tower-opencode/docs/superpowers/plans/2026-11-02-opencode-adapter.md | `31369e1af8988d13fe97a20eeac5ef03723ae210d340a0b01b9521c94994a813` |
