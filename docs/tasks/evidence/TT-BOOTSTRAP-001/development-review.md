# TT-BOOTSTRAP-001 independent development review

Reviewer: bootstrap_final_review, distinct from executor. Date: 2026-11-01.
Verdict: ACCEPTED for development scope at the file hashes below. No unresolved Important/Critical finding identified.
Reviewed working tree based on HEAD 929da1ae8094baed55cdc89c9e59d66d183992cb. No commit, push, model call, main integration, or production source edit performed by reviewer.

## Scoped re-review and resolved findings

The earlier Important Python 3.11 junction issue is resolved: harness._state and tasks._safe_path use os.lstat and Windows FILE_ATTRIBUTE_REPARSE_POINT, independent of the Python-3.12-only Path.is_junction API. Actual Windows junction regression tests passed with Path.is_junction forced false, and the harness test verifies that the target directory remains untouched.

start.cmd now uses labels outside parenthesized blocks and propagates the interpreter exit code using exit /b %errorlevel%. Its invalid-argument exit-code regression passed. Static review confirms this also propagates ordinary child return codes. The separate tester's extended launcher exercises remain separate evidence.

load_task revalidates accepted postmerge commit syntax and ancestry against current local main. The regression rejects both a missing stored commit and a renamed/absent main. Reopening an earlier stage clears downstream acceptance and can repair an obsolete card.

## Other reviewed behavior

Non-TTY launch requires an explicit mode; launch/configure/dry-run are mutually exclusive. Saved skill hashes are checked on reuse; explicit skill selection permits repinning. Adapter snapshot is validated and never implicitly reread. Custom argv preserves argument boundaries, permits only the two documented format fields, and uses shell=False. Builtin prompts start with fixed text; project paths do not become options. Native Windows executable restriction is explicit. Atomic replacement avoids truncating hardlink targets.

Documentation accurately limits identity, provenance, telemetry, supervision, autonomous workflow, and cross-platform claims. CI contains all three operating systems but has not been observed running by this reviewer. Platform shell entry points were inspected; Windows start.cmd was exercised by its subprocess regression. No actual model/harness account or overlay launch was attempted.

## Independent verification

Executed on Windows using bundled Python 3.12.14:
`python -m unittest discover -s tests -v`
Result: 56 tests, OK, 1 skipped (symlinks unavailable), 16.133 seconds; exit 0. Both actual junction regressions, launcher invalid-argument propagation, fixture harness exit 7/context/cwd, and postmerge invalidation regressions passed. Python 3.11 itself and macOS/Linux were not executed here; compatibility of the corrected detector was additionally assessed from its API usage and simulated missing pathlib detector. This is development acceptance, not postmerge or night-readiness acceptance.

## Reviewed file SHA-256
- task_tower/harness.py: `89e2792875cd2bf2d5a18e638b6894e775e1ef67b1e79ec1c6643bd762125ddb`
- task_tower/tasks.py: `e4f7c4160670710b07c26e4ec76f6800fbdb0343376f997dc4eaa85df1672f46`
- task_tower/bootstrap.py: `917963347081134ffd578220e4734d78cecb156771c1da9fc803174556bd322f`
- bootstrap.py: `5df8d016d1e46343792c01bdc598e1d24881e9108486b0bbce81035ed08b5da2`
- start.cmd: `c6616cb26097c265ae968466eb93ceabdbf5c14082ef7f703334d15d14b02ef0`
- start.sh: `587f1d028c8b5f8c19333c7b6ddfe3ce71f5ab5d0905c90d9872044231999b37`
- task_tower/__main__.py: `e51a22a726ecc5fa5e0681ee938b565523452bad5ccde02c5c02a00aae0306f7`
- tests/test_harness.py: `996a7a43900434c6b6a8e31c07a04224dd56a66cb2d2119aed766c3a9dd56ae5`
- tests/test_tasks.py: `2c4f89c6017034ed300b0d0b73215077cafffb08fe3f28f2c60e1a27f266797a`
- tests/test_bootstrap.py: `fe2e098c45c936be049c7524ac36d9506504f087cc55fb3488570430244ace73`
- tests/test_task_cli.py: `cbd6268521debad9b5bbae6b7120535b043f0ae6e6d991eb6b756915e763aaad`
- .github/workflows/cli.yml: `793c93fe5376cb227d066e17e821ac57d4137768bca64d25ae3b338c965f15c8`
- docs/bootstrap.md: `0e2b7821c8e6c446e8637cfa1e9f9ecb13bbbc8bdcf9737cb614b18f85545988`

