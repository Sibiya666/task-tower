# Independent development review — TT-PROJECT-ROLLOUT-001

Reviewer: onboarding_code_acceptance, distinct from implementer. Date: 2026-11-01.
Baseline: 4544611ac81294cb6b7dcf85b7afab3397496a54.

Decision: ACCEPTED for the exact reviewed file SHA-256s below. No unresolved blocking development finding.

Reviewed the whole actual changed/new production, test and documentation diff, including bootstrap/CLI forwarding, books import output, safe private connection writes, Project discovery/creation/status preservation, repository-local Issue identity repair, proof-default denial, and honest capability boundaries. Runtime test logs are excluded.

The original P1 was corrected before this acceptance: both Project and Issue creation now commit a durable SQLite intent before the remote POST; an unresolved or resolved-but-disappeared identity cannot authorize another create in a fresh invocation. Unique remote discovery reconciles the retained intent; no reset/delete is automatic. Canonical repository node IDs scope identities, and the Project identity key survives repository renames. Added tests exercise fresh-invocation empty discovery and subsequent late visibility for both resource types.

The journal rejects symlinks/reparse paths, hardlinks and unrelated SQLite databases. Resolved resource IDs cannot be silently replaced. Post-create local journal failure retains visible Issue/Project identity and an actionable partial result. Documentation states journal retention and movement requirements and preserves the explicit cross-host serialization limitation.

Official GitHub Projects schema checked: existing single-select option IDs preserve identity, and createProjectV2 supports repositoryId. Source: https://docs.github.com/en/graphql/reference/projects#projectv2singleselectfieldoptioninput .

Validation: final stable-source focused onboarding/bootstrap/import suite passed: 55 tests. An additional full CLI run passed 254 tests with 2 skips; that full run overlapped final amendments, so the separate independent test reviewer must bind its own fresh full run to the final source. No live GitHub mutations performed. This is development-stage acceptance only, not live rollout, PR head/base, cross-platform CI, main or postmerge acceptance.

Reviewed SHA-256s:

- `AGENTS.md`: `e18c91be68571364d7e6517af5ec76e2f87b07f9cfc487890e50e411f34ccfff`
- `docs/bootstrap.md`: `150d6e6a7343ed992de68b96d8fd7345b3340abd93c956fd5d09dd7bdec06806`
- `docs/github-books.md`: `d109e4b0f60036437d8181d3191a795004e251519026a643a6d7fdc90d15d3e0`
- `docs/github-setup.md`: `2aebfcdcdf03291c563aabf5314e7054598df55e87de62a2ec4f423568d178cc`
- `docs/roadmap.md`: `b619564072e80098b8c3bcb08e3bb06d73fe4ad5fd72da7caec88e1a0b42b3b5`
- `docs/superpowers/plans/2026-11-01-project-onboarding.md`: `5e8a5e69869734c2c40e8308713953a1805c29e33dc83e88751a3124540f5959`
- `docs/superpowers/specs/2026-11-01-agent-development-architecture-design.md`: `d8c60f6c815b540518f2daafbb24e1cc6d35c091897f8983962a9b52e0469ef6`
- `docs/superpowers/specs/2026-11-01-project-onboarding-design.md`: `5481a7debe890f601039dc25f0ad6894ce5859e3db0b5ad76894801d703fa85f`
- `docs/tasks/evidence/TT-PROJECT-ROLLOUT-001/spec-review.md`: `7871e8eb15ded6f65930b2954cbae71d2acb81ea7952cb3c5f3e5b7c479a708c`
- `docs/tasks/TT-PROJECT-ROLLOUT-001.json`: `1b97975627fdeeb564ebe3e70acfcea0af027f2cfb6182f7cfc4b65145896cbd`
- `README.md`: `ea9da721b0ee8b32690de8994f45b105cd23617e55e1e1bdc725930f6070a08d`
- `task_tower/__main__.py`: `19597381bf7fa352ab6e4e9a7cf3a1c247815334374b5ee4a1339398a0c65ff4`
- `task_tower/books.py`: `d5e1a55abfa281c4628464f102c16377276681a8a0394ce9499f9a1efc76fab9`
- `task_tower/bootstrap.py`: `8881457b237dc5b31e83fd97b6115d3e33a5b489844e9f1d78250bf607193dc1`
- `task_tower/creation_journal.py`: `b2fc2f68151f2d63415a727914fe17ec123d4ad64f428eb62274576db1975f51`
- `task_tower/github_tasks.py`: `a177a83b16c1aa2e10f7cd85d5a31b379c597506cf6a4c8bc45cc6c236979a1e`
- `task_tower/project_connections.py`: `41d4efcf25021e1147ebfd22d32c5541f628f8991d0c59fe11e45118db7520c9`
- `task_tower/project_onboarding.py`: `65dcbdb110a5f8069d3efdc3fc961b0d34013fd3563b189085272d3d9e048f38`
- `tests/test_bootstrap_connections.py`: `d2949f776066bfb27ece77f7029edbf7f82a61ba5f2c6277cd2a7ae67ec1bd59`
- `tests/test_github_projects_acceptance.py`: `158d46f0483ef4f0dac34f73eb6a0b1bace1b0b1045f5cbe7505a628bf24753e`
- `tests/test_github_projects.py`: `00664d368500ceeb4a7df3147ccbe2b372957f3fab21f8ab4456a61cdfc02a2e`
- `tests/test_project_onboarding.py`: `306b8219fd68381c034c7219e40dfddaa1b76eb04d06b43da3c7f59c65a35e61`

## Development acceptance supplement — 2026-11-01

Decision: ACCEPTED for the macOS fixture correction. Independently reviewed the complete follow-up diff: 9 insertions and 6 deletions across the two test files below. TemporaryDirectory roots are resolved once before constructing connection/card paths or passing checkout arguments. This correctly uses the canonical physical temporary directory on macOS (where /var can be a symlink) while retaining the production requirement that private configuration paths reject symlink/reparse components. The fixtures retain their original assertions and test behavior; no production files changed.

This supplement supersedes only the earlier SHA-256 entries for these two test files; all earlier review history remains intact. The independent test acceptor owns the fresh full-suite and platform CI evidence. No additional blocking finding.

Supplement reviewed SHA-256s:

- `tests/test_github_projects.py`: `85bf1628e0a18008bb3a31ecd5c1d3dd0a84db8481b5c7b220457060aefa045e`
- `tests/test_github_projects_acceptance.py`: `d4b6588901dff86009d3373f5a30c41023535c6cd43411ea8ad8a37be1ad0739`
