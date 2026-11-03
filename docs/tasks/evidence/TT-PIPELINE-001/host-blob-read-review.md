# Independent host Git blob-reader review

Reviewer `/root/books_native_smoke_impl`, distinct from implementer; 2026-11-02. **ACCEPT the frozen one-line production correction and its tests.** This is source review, not a successful retry of the preserved installed-model pilot.

HEAD `25be4657bbf5812dd2029c23b6b7c3f0aab93e06`; supplied main base `56f8ab12f21ab91030ffe54de96520fcd979dc04`. Freeze `runtime-task7-blob-freeze.json` SHA-256 `eb1e69cb7ed839caf9ed75d6d11fa62e469c58770dbbf9ad4f8f9df3209aff7c`.

| File | Raw and canonical SHA-256 |
| --- | --- |
| task_tower/pipeline_publish.py | `b2334db53619d698cf2e88719459d9533a0ed0cc0aff885a085cd0d981e43603` |
| tests/test_pipeline_publish.py | `0f183332178247a671a0c2aa268a578b8316b87092936f29ecd89fab91d6a841` |

Independently checked the exact bindings and entire two-file diff. `_commit_object` changes only its evidence-blob read from `git show SHA:path` to `git cat-file blob SHA:path`. The latter explicitly asks Git for the object bytes and avoids the ambiguous filesystem-stat path. Parent, current branch, tree, commit size/message, exact changed-file set, projection identity and exact byte-equality guards remain intact. No settings, authority, verdict, credential/sandbox, process or journal semantics changed.

The preserved read-only mechanism diagnostic SHA-256 is `96f0ae117559d51cd5924fdda71d593f6cd1decd9bf563b6137dbc0e182dcf7c`: cwd length167 plus object argument103 and separator totals271 characters. The actual evidence file remains accessible. The original unqualified `show` exits128 with filename-too-long, while explicitly disambiguated `show ... --` and typed `cat-file blob` both return the exact 1485-byte projection. This is a Git revision/path disambiguation failure observed on Windows, not proof that the artifact is corrupt or permission to change `core.longpaths`/OS configuration.

## Independent verification

Absolute cached Python, from the repository:

```text
-m unittest tests.test_pipeline_publish.HostCommitBlobTests tests.test_pipeline_publish.ContractTests tests.test_pipeline_publish.PublicationTests.test_projection_does_not_change_accepted_product_hash tests.test_pipeline_publish.PublicationTests.test_completed_host_commit_recovery_preserves_stage_checkpoint tests.test_pipeline_publish.PublicationTests.test_final_commit_crash_after_ref_is_observed_without_mutation -v
```

**8 tests in 89.218s, OK, exit0.** Actual Git tests cover normal and Windows long-cwd/short-separate-git-directory reads; forged parent/tree/message/file set/blob remains rejected. Existing publication identity contracts, unchanged accepted product, completed-checkpoint recovery and post-ref crash observation pass. An earlier reviewer invocation selected two nonexistent test names: five real targets passed and two loader errors occurred. The corrected complete eight-target run above is the reported verification; those invocation errors are not product failures. Author 10-test/214.340s evidence is separate from this independent run.

Independently reconstructed the old V2 projection and called the actual `validate_publication_current` read-only after this correction. Validation succeeds for checkpoint `532880fd0b9ff63db98ded1277b4e62c1c0ea83e`, projection manifest `0c9e272bcb41dc6466efecf9b1294490feceab9d6485def11e7df1e62ea3fcda`, and its 1485-byte file SHA-256 `80b2783b446c5587ca3263642626e726b565856aaff0ccff7083dc6f49d51251`. Journal hash is identical before/after and state remains `needs_input`. The author's corresponding preserved diagnostic SHA-256 is `4dc8f2c8a7c8f756a732cd1b53a3f6ca162e6c44a37b403a534a7c33220c7383`.

All 445 V2 and 166 original negative-pilot file bindings remain unchanged. No role, publication action, reset/resume, ref update or state transition was performed. A read-only successful observation of an old completed object is **not** a new `ready_for_pr` outcome. A separately authorized preserved experiment and later integration gates remain necessary for that claim.

No source edits, settings changes, installed-model launches, commits, pushes or external writes were performed by this reviewer. Changed bound inputs invalidate this verdict.
