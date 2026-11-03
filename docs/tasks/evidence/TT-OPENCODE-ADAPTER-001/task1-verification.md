# Issue21 Task1 verified test receipt

Scope: configured-only OpenCode policy/parser and pre-PROBE host metadata; no native OpenCode execution or installation qualification.

The Root-owned contained runner executed `python -m unittest discover -s tests -v` on integrated candidate HEAD `396e7414eb5dbcd41ee5ce6c6cd218dd078924de`, containing accepted main `7586df4ac2e59316521463b7526089c8314024e4`. Actual unittest output: **814 tests in 1554.067s, OK (skipped=7)**. Completion reports exit0, cleanup_confirmed=true, verified_success=true and source_unchanged=true; no truncated capture or unknown tails. Runner release is accepted main7586df4; runner SHA256 `b6431c2737f223f0bf7dbfa66602d2ffe0ba2289559c8f00d483755db79a49db`.

The independent Task1 reviewer subsequently checked the completion fields, both complete capture digests, identical before/after input manifests and every current captured source/test hash. All17 frozen candidate hashes still match the independent review. The integration changed accepted-main fetch recovery/docs, preserving the reviewed Task1 bytes. Documentation/evidence preservation below changes no product/test behavior and does not justify another full-suite run.

Local private artifacts: runtime/verification/opencode21-task1-final-root/{completion.json,inputs-before.json,inputs-after.json,stdout.log,stderr.log}. Only their nonsecret receipt and hashes are preserved here; raw logs remain private.

| Artifact | Raw SHA256 |
| --- | --- |
| completion.json | 637a2e4515f542b8e8e32f9c1d0890f8845e081e15de4d3f05c90f005f29aa2f |
| inputs-before.json | 818c542f3d2f171d3a95a1a79552f880e815e420ac9a9dbd1eff28a5dd886b9a |
| inputs-after.json | 818c542f3d2f171d3a95a1a79552f880e815e420ac9a9dbd1eff28a5dd886b9a |
| stdout.log | fd546d01c6d2880b01d3bce9a7b1f43d0c4125bcc137c4ce97d019d3e8643e08 |
| stderr.log | 761869bfd6272c271ac29be80db4cc176db33f42093360d6f0d001deac0d5282 |

Independent review is preserved byte-for-byte in [task1-independent-review.md](task1-independent-review.md), SHA256 `8a68c7b922b69cc10f9bdfbaab2873b227ab09c4fecb291e577f79152ac4a97a`. Its 76-test targeted result and exact17-file hashes remain distinct from this Root-owned full suite.

This receipt accepts neither a whole Issue nor a native installation. Collector revision is semantic; pinned report bytes/reviewer prose cannot establish independent provisioning or installed implementation equivalence. A distinct installation qualifier must review the exact source/collector/tool policy and the coordinator must provision accepted exact private pins. Unsupported startup/log/state/KV/database/plugin influence and absent installed binary proof remain blockers. Task4 requires actual version evidence, host-owned physical continuity and fresh prelaunch checks plus separate run permission. Tasks2-5, native task/reviewer qualification, future CI/PR/head/base/main/closure gates remain separate.

Commit preparation: `git diff --cached --check` reports the existing reviewed extra blank line at EOF in tests/test_opencode_templates.py:141. The frozen accepted source bytes were preserved; no whitespace or behavior rewrite was made. README/AGENTS documentation diff check is clean.
