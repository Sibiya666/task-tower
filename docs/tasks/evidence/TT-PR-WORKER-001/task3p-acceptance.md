# Task3P bounded implementation acceptance

Status: independently accepted pipeline subset with a verified Root-owned full regression run. Task3L remains a current unmet requirement; whole Task3, Issue17, Task6, PR/main integration, installed pilot and unattended readiness are not complete.

## Exact candidate and independent reviews

Candidate baseline HEAD: `f148710c691294662dd0198272b65b4e15c785c2`; accepted main foundation: `7586df4ac2e59316521463b7526089c8314024e4`. The preservation commit containing this document adds these exact reviewed product/test files and their evidence; it does not introduce Task4/controller behavior.

- [Historical accepted-main binding review](accepted-main758-binding-review.md), SHA256 `58984df38805f74221c839eca90d388bafad0c5687e665c9d00b6aab5aadab9c`, remains preserved with its original scope.
- [Current full-profile/legacy-gate spec review](full-profile-legacy-gate-spec-review.md), SHA256 `1bab4e3196d983d87d3d6384f2e3e8f2dab87e07a82281b047eaf59094cdd5c0`, approves exact spec `1227662a39703bdceca60182e3d599c5330b4243b93e40e7e991ef80a0e5b1ba` and plan `00b334e8604b4429861968a5e5656dd8656775a3cbff4114aa75affed240c287` plus the linked Task3L evidence gate.
- [Independent code review](task3p-code-review.md), SHA256 `045788ad6308bfb7c57c6154693b67c9e64a7128de8c0c6f024a11d67a116170`, APPROVES only the 13 exact frozen files enumerated in that report. Freeze SHA256: `f4021eba768614fa696a71cc5f0d6492ec24709bd9c47b694b4cfd43e42fcd0d`; review-package manifest: `0c242e205378b4cb4ee0fc107b09aa0dbcc8ff674995f90562ed223b1c24b7dc`; tracked diff: `67ad4f3677dd41f1a068a2f3ea68146cf96e32a882aeee16db80a39ecadab341`.

The implementer and reviewer were distinct. Before preservation, all 13 raw candidate hashes were recomputed against both the freeze and Root full-run input manifest. The additional changes after the run are this evidence preservation and bounded README/AGENTS/ledger documentation only; production/test sources remain unchanged.

## Verified behavior and preserved contracts

The subset validates genuine pinned read-only PipelineJournal state in one explicit transaction, retained role/check artifacts and independent accepted stages, immutable contribution/publication Git objects and the observed PR binding. It reproduces the sole actual host MD and projects its three stage records into an untracked private v1 card without overwriting tracked cards.

Bound ReviewRunner/review_one consumes the actual Task1-loaded normalized Codex/custom profile and complete pins, copies and revalidates every instruction member and raw snapshot, enforces the fixed readonly invocation and distinct instance/process/request/effect/result envelope, and fences bare/orphan/unknown attempts. Default APIs remain unchanged. publish_step separates durable comment POST and Issue-close PATCH across calls, never replays ambiguous effects or takes an expiring legacy claim, and requires genuine verified_done/current main/lifecycle proof for publication completion. The future controller still owns final repository-barrier completion.

The [source-contract audit](task3p-source-contract-audit.json), SHA256 `9135defc57a03417d2c5d61a1071c85878b985b1f90ed6fbbe8c812bf12ee5f1`, records 17 accepted execution/storage/task modules raw-identical to accepted758, unchanged legacy review/publish method ASTs and all six pipeline SCHEMAS. Schema digest remains `5b37731384a2d5a8aa87f38f589bcced2b78db2205861e6aa5290d4b4ccdc9b6`. No live journal/schema migration, native/model invocation, credentials or GitHub effects qualified this preservation.

## Root-owned complete regression evidence

Command: `python -m unittest discover -s tests -v` (Python 3.11+, no installation). Root ran it independently of the implementer under the accepted758 contained process runner; the implementer's separate focused run had 91 tests, 355.857 seconds, OK.

[Complete-run receipt](task3p-full-suite-receipt.json), SHA256 `e2ed4890b011016bc0a22c06933ff543fe780cd54efb14eff1f89e59d617a0b2`, records verified_success/source_unchanged true, exit0, actual PID62736 and cleanup_confirmed true. The complete footer is **853 tests in 1878.951 seconds, OK (skipped=7)**. Full stdout/stderr were captured, with no truncation or unknown tail. Outer elapsed time: 1879.469 seconds; runner SHA256 `f46049aa320ad3e57b3c9e1ddcf4467babd118797d8dfaa71a8a39a0d362ee33`.

- Before/after complete input manifests are identical: SHA256 `ea0c8bff54abcad018ef118b11f47724913db8969e97453adf45a9bd3dc85450`.
- Stdout: 85 bytes, SHA256 `fd546d01c6d2880b01d3bce9a7b1f43d0c4125bcc137c4ce97d019d3e8643e08`.
- Stderr: 131668 bytes, SHA256 `aa690d4a3eab7abff8dbc4eb5b708f73cd1d77f086eadcbeecc0f680e2655768`.

These capture lengths and hashes were recomputed from Root's retained logs before preservation. The seven skips cover unavailable symlink privileges (five cases), a POSIX executable-mode transition and an actual unsupported-host regression. They do not provide native macOS/Linux qualification. Generic portable three-OS CI remains required at integration; no new native pilot is claimed here. Complete raw logs/manifests remain in local runtime verification storage, outside Git.

## Remaining gates

[Task3L](legacy-provenance-gate.md) remains mandatory and unfulfilled; its [wire proposal](legacy-provenance-binding-proposal.md) remains unapproved research. Existing unsupported legacy admission refuses `stage_authority_unverified` before effects. Importer trust, labels, copied JSON or new identities cannot invent original historical process authority.

Independently accepted Task3P can support pipeline-only Tasks4/5, without marking whole Task3 or Issue17 complete. Actual PR controller/merge effects, Task6 installed behavior, fresh eventual PR/main acceptance and automatic Issue closure remain separate later gates. Genuine all-main-writers operator authorization and effective strict nonbypass server protections have not been set up or attested by this work. No push or external publication is included in the local preservation commit.
