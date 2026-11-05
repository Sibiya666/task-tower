# Windows Harness Qualification B Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bind the installed Windows 10 Codex interface and independently establish the exact remaining capability gap before any native/model qualification launch.

**Architecture:** Use the existing installed executable and accepted bounded process helper for four fixed identity/help commands. Produce an independently reviewed capability-gap result, stopping at mandatory unknown guarantees. A future exact native/model manifest requires separately established containment and independent review. Receipts describe observations and never become a second queue or executable authority.

**Tech Stack:** Current Windows 10, installed Codex CLI, existing Python standard-library process helper, UTF-8/JSON/SHA256; no installation or SDK.

**Spec:** [Approved unified design](../specs/2026-11-05-task-tower-unified-design.md), especially the dated approval notice and sections 5–6. Its approval supersedes historical fixed-six-role wording; it does not qualify PR85.

## Global Constraints

- “ACL, аккаунты, модель, авторизация, credential scopes и установки не меняются без отдельного соответствующего разрешения.” No such new permission is supplied by this plan.
- “Разработчик не принимает собственный результат.” Agent count follows the task; no six-role mandate.
- “unknown обязательной гарантии блокирует C”. Required security is not a negotiable subset of the qualification.
- “Worktree и post-run hash сами по себе не enforcement”. A prompt prohibition, environment filtering, JSON grant or source hash cannot replace containment.
- “Проверки доступа используют разрешённые несекретные canary-данные, не чтение настоящих секретов.” No private config, authentication, database or raw-session inspection is authorized here.
- “При потере ответа сверка фактического исхода и stop вместо повторного эффекта.” No resume/retry or replay of unknown attempts.
- Accepted baseline is `ab91f551fb10e18622e2251e7d4709a2f2c380fb`. PR85 head `cf560243756026fd0ea1a6f585e2fe16a33ddfb9` is an unqualified candidate. These are supplied snapshot identities, not a fresh main/PR check.
- Preserve Beads ownership/history and original receipts. B performs no admission claim, merge, task closure, old worker activation or product-readiness declaration. Existing delivery/PR/main gates still apply to later code integration and C.

## Review Focus

1. A version string matches while executable/helper bytes differ: fail identity binding before launch (I1).
2. A receipt belongs to another binary/helper/plan: reject the binding; future artifact/task binding remains unqualified (I4/F1).
3. Native shell denies access but another enabled builtin/plugin/delegation path can read it: require complete enabled-route coverage, otherwise block (G1).
4. An ordinary external sandbox client refreshes shared permissions during a live run: a Task Tower mutex is insufficient; retain the unresolved guarantee (G2).
5. Parent exit or truncated streams conceal living work: record unknown, stop subsequent inventory commands, and leave real cancellation qualification not-run (I3/F1).

## Evidence and current decision boundary

Read only these existing sanitized inputs, under workspace `runtime/`: `architecture-audit-20261105/execution-interface-inventory.md`; `beads-stage-20261105/backend-prerequisites-alpha6.json`, `win10-current-status.json`, `minimal-adapter-builder-assessment.md`, `legacy-public-contract-inspection.md`, `cross-source-cwd-pair-report.md`, `PRIVATE-GUARD-AUTHORIZATION.md`.

They establish limited positive legacy primitives, failed MXC startup, paired error267 before either helper, and unresolved cancellation/coexistence. None establishes comprehensive private-store exclusion for a real model. Tagged public source is not installed-build provenance. The prepared synthetic USER-SID guard has **no application authorization**; even successful application would not protect the original stores. Do not execute its CheckOnly or Apply path as part of B, repeat the failed pair/MXC probe, or inspect denied private configuration to fill gaps.

**Current expected result:** inventory may succeed, but G1/G2 remain blocked on supplied evidence. Full B qualification without new rights is not presently established. This is an evidence-based limitation, not proof that Windows 10 is incapable. The plan permits a supported existing-rights solution only when new authoritative evidence actually resolves the listed gaps; it does not authorize experimenting until one happens to work.

## File map and budgets

The plan is the sole repository addition in this work package. During I2 preparation, create one new local directory `runtime/architecture-audit-20261105/qualification-b-first/` (workspace-relative; fail if already present). Create it once and retain existing evidence unchanged. At execution, allow exactly the independently reviewed `run-inventory.py` and `preparation-report.md`; refuse preexisting captures/results or any other entry. All files below are local evidence, excluded from commits and model-visible scope.

| File | Responsibility |
| --- | --- |
| `run-inventory.py` | Four fixed help/version commands using pinned accepted helper; no sandbox/model execution |
| `preparation-report.md` | Exact runner/input pins and independent preparation review provenance |
| `inventory.json`, `inventory-captures/<case>/` | Binary/helper identity, complete bounded public help and genuine process receipts |
| `gate-review.md` | Independent G1/G2 decision with evidence links, scope and unresolved guarantees |
| `qualification.json`, `qualification-review.md` | Source-bound capability gaps and independent final report review; no qualified verdict in this pass |

Use only this fresh root; no recursive private-directory discovery. Runtime helper code, if required, is reviewable test preparation, not a new product adapter or queue. If a continuation requires product transport changes, stop B and prepare the specific change separately against the approved spec; do not silently adopt PR85.

| Budget | Limit |
| --- | --- |
| Inventory | 4 subprocesses, 10 seconds each, total 60 seconds including cleanup; one attempt each |
| Read-only public contract follow-up | At most 4 specifically named official resources, no guessed-path retries; then decide G1/G2 |
| Native/model execution | 0 sandbox probes, 0 model sessions, 0 setup/ACL/config commands in this pass |
| Cleanup | Existing supervisor's 5-second cleanup/EOF deadline; no next command while outcome is unknown |
| Data | Captured prefix at most 65536 bytes per stream per command; any truncation blocks parsing/pass |
| Cost | 0 model requests and USD 0 model spend; no installation/purchase/billing changes |

Output exceeding a cap or missing EOF is incomplete evidence, never a parsed success. Spend, elapsed time and launch counts accumulate across the whole attempt and are not reset after an error. No automatic retries. Stop on the first failure/unknown/unsupported capability, preserving all produced evidence. Numbers are qualification limits, not a new global task-slot policy.

### Task 1: Bind the installed interface without launching a model

**Files:** Create `run-inventory.py`, `preparation-report.md`, `inventory.json`, and per-command captures in the fresh root. Reuse accepted `task_tower/processes.py`, `windows_job.py` and package `__init__.py` from the coordinator-identified snapshot `runtime/pr84-main/source/`, after byte comparison against baseline Git objects before import; do not import the PR85 checkout. Use the already installed interpreter `C:/Users/sibiya666/AppData/Roaming/uv/python/cpython-3.12.16-windows-x86_64-none/python.exe`, expected SHA256 `246221B571E7A692A8B26818B628CAC4C163E836DE9897812EAEBC2A8E1EFA90` supplied by the coordinator's independent read, rechecked before use. These paths identify inputs, not a claim that this author refreshed their hashes.

**Interfaces:** Consume fixed executable path and expected digest below. Produce `inventory.json` with `schema:1`, `kind:"interface_observation"`, expected/actual executable digest, actual version, source/helper/interpreter digests, command case IDs, actual process results, and `model_requests:0`. Never mark `qualified:true`.

- [ ] **I1 — Check source and binary identity.** Read only the exact accepted Git objects for `processes.py`, `windows_job.py` and `__init__.py` and compare them with the source actually imported. Pin the chosen already installed Python interpreter and resolved nonlinked executable. Do not copy or import a changed candidate helper. Expected executable: `C:/Users/sibiya666/AppData/Local/OpenAI/Codex/bin/a159911ff70742e9/codex.exe`; expected SHA256: `925c7d0665ffa49b0dcf748e034a805a04da984164ac92301432073b47789b99`; expected version: `0.166.0-alpha.6`. Missing/mismatched identity stops, with no search for another install or model. Do not read adjacent private files.
- [ ] **I2 — Prepare and independently inspect the fixed runner.** Use `run_command(argv, cwd, timeout_seconds, env=None, *, cancel_requested=None, capture=None)` from accepted source, optional capture mode, timeout 10, `cancel_requested=lambda: False`, capture cap 65536. CWD is the fresh evidence root. Pass explicit environment copied in memory with case-insensitive `GH_TOKEN` and `GITHUB_TOKEN` removed, never print environment values; no `-c`, permission/model/auth overrides or shell. Record local interpreter/helper digests. Reviewer checks fixed argv, no setup/config/private reads, and refusal before execution on mismatch. Do not execute a runner whose source changed after review.
- [ ] **I3 — Run exactly these argument arrays serially:** `[exe,"--version"]`, `[exe,"--help"]`, `[exe,"exec","--help"]`, `[exe,"sandbox","--help"]`. No `sandbox` command without `--help`; no `exec` prompt. Each case must return actual exit0, complete stdout/stderr, cleanup confirmed and no cap overflow. Stop after any refusal/error; do not try guessed replacement flags. Verify executable/helper pins again afterward. Version/help programs may use the installation internally; this step authorizes no explicit configuration inspection or changes. Any setup/auth prompt or unexpected effect stops the inventory.
- [ ] **I4 — Record supported interfaces precisely.** Extract only observed help lines for prompt delivery, result transport, permissions and approval controls. Missing flags remain unsupported. CLI help demonstrates syntax, not security or default enabled tools. Record actual facts with hash/byte counts and mark all native/model guarantees `not_run`. Independent review accepts or rejects this observation before Task 2.

If the outer execution sandbox cannot run the named installed executable/interpreter, a normal tool-level escalation for these exact read-only commands may be requested with the same paths, limits and token filtering. It grants no ACL/config/setup/model action. If automatic review rejects it, preserve the rejection and stop; do not change tools or environment to bypass it.

### Task 2: Resolve the mandatory containment gate or stop with a concrete blocker

**Files:** Create `gate-review.md`; no native/model invocation manifest in this pass.

**Interfaces:** Consume accepted inventory and named sanitized reports. Produce an independent capability table bound to plan/inventory/binary/helper digests, with `established|unknown|unsupported` for each guarantee and `native_launch_allowed:false`. This table is an observation, never qualification or a substitute ACL grant.

- [ ] **G1 — Build the installed enforcement table.** For each enabled model I/O path (command execution, file/image reads, metadata/listing/walks, MCP/plugins, network and any delegated tools), identify the actual enforcement boundary and authoritative installed-build/profile evidence. Require bounded allowed source/output writes, reviewer read-only access to actual source and executor result, prohibition on writing host receipts, model exclusion from original DB/config/auth/private evidence, no credential propagation, no unapproved escalation, and no unrestricted alternate tool route. Trusted existing harness authentication is separate from model-visible file/tool access. Do not inspect real secrets or infer protection from a synthetic root. If any enabled route or original private store remains unknown, record the exact blocker and continue only to the final report.
- [ ] **G2 — Establish lifetime and external-client guarantees.** Require supported evidence for the exact installed binary/helpers covering permission identity, scope/lifetime, ordinary external-client refresh, child/grandchild containment and revocation/error behavior. Check for newly required ACL/setup/identity changes before any command. The supplied tag analysis and failed paired run do not meet this gate. An internal mutex, lack of another client in a process snapshot, or manually closing desktop clients does not meet it either. No repeat of MXC/refused default-deny/error267 experiments without a materially changed, supported premise and independent review; that would be a new plan revision.
- [ ] **G3 — Produce the stop record.** Current sources warrant a stop record naming at least original-private-store exclusion and external-client/lifetime evidence as unresolved. Identify what authoritative installed-provider statement or concrete separately permitted operation would resolve each; do not claim the pending fake-root ACL alone resolves them. If new permitted evidence materially improves the result, record it accurately for a later exact manifest rather than launching under this inventory plan.

### Task 3: Independently classify the gap and stop this pass

**Files:** Create `qualification.json` and `qualification-review.md`. No product, native/model, Beads or Git mutation.

**Interfaces:** `qualification.json` carries `kind:"windows_harness_qualification"`, exact observed provider identity, per-criterion `pass|fail|unknown|not_run`, evidence digests, actual budgets, `outcome:"blocked"`, limitations and next permitted action. Independent review binds to this file and the complete evidence manifest. This pass cannot produce `qualified` because native/model execution is excluded.

- [ ] **F1 — Reconcile all required criteria.** Map every spec section 6 row and negative case to the inventory, named prior evidence, or `unknown/not_run`. Inventory success, isolated primitive success and schema checks remain partial observations. Unknown security, missing actual independent model review or incomplete lifecycle prevents qualification. Hashes establish identity, not isolation.
- [ ] **F2 — Obtain independent final review of the blocker.** The acceptor reads actual inputs/results and checks source binding, budget compliance, honest not-run cases and a concrete next action for each blocker. Approval means the report is accurate; it is not provider qualification. Any changed byte invalidates the affected review. Preserve PR85 HOLD and C blocked.
- [ ] **F3 — Leave a narrow future gate.** A subsequent continuation requires an independently reviewed exact invocation manifest based on newly established installed containment, not guesses. It must fix executable/helper/profile/input hashes, actual argv/API/transport, CWD and allowed scopes, live authority, all enabled tool routes, input/result binding, numeric time/attempt/output/cost budgets and the expected result of every case below. It is not created merely to make this pass look complete. If a new ACL/setup/account/config permission is actually required, specify the exact delta for user decision; the existing synthetic guard request supplies no permission and does not resolve original private stores.

| Future case, only after the gate | Required real evidence |
| --- | --- |
| Unauthorized input; stale/mismatched result | No launch for unauthorized task/source; result bound to task/attempt/source/criteria; no acceptance from executor self-verdict or model-selected paths |
| Access and evidence integrity | Allowed source/output operations and actual denied reads/writes on nonsensitive canaries through every enabled route; original private-store protection established independently; reviewer cannot alter source, executor output or trusted receipts |
| Permission lifetime/coexistence | Exclusion before/during/after an ordinary external-client refresh, including a canary created after startup; real overlap, known installed enforcement, no internal-mutex substitution |
| Cancel, timeout, parent loss | Bounded stop, actual child/grandchild and broker lineage, complete streams and cleanup; exit0 alone never proves cleanup |
| Unknown effects | Original outcome reconciled from bounded genuine evidence or retained unknown/fence, with zero replay launches |
| One real executor and independent review | A small precommitted harmless UTF-8 brief/source and checkable artifact, separate real session identities/contexts, actual source/result digests, independent substantive verdict and enforceable cost limit |

These are acceptance obligations for the later manifest, not runnable instructions or an invitation to repeat failed probes. Variable agent count applies; the accepted spec does not require six sessions. Full B requires all section 6 guarantees, then an independent provider/profile-qualified verdict. Even that does not by itself close all of `tt-auq.2`: retained coordinator obligations need their explicit crosswalk. C still needs real admission/claim, useful delivery, CI, PR/main and Books evidence under its own plan.
## Plan self-review and execution handoff

Spec coverage: I1–I4 bind identity and observed interface; G1–G3 classify security/lifetime gaps; F1–F3 preserve every remaining section 6 obligation explicitly as unqualified, with a concrete future gate. This is the first bounded step of B, not its full completion. Section 7's real Beads-to-book delivery remains C. Historical six-role text remains source history, not a new gate.

This plan needs independent byte-bound acceptance before execution. The user has already authorized routine execution through independent acceptance; no new general confirmation is requested. A concrete operation outside existing rights, if actually needed, must be presented with its exact effect and reason, after completing available authorized preparation. Until then the supported path ends at a truthful blocker, with no model/native experimentation.
