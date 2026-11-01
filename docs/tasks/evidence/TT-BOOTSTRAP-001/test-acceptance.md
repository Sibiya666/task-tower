# TT-BOOTSTRAP-001 independent test acceptance

Reviewer: bootstrap-test-acceptance (independent from executor). Date: 2026-11-01.

Result: PASS for local Windows bootstrap test acceptance after wrapper correction and retest. No source files or task status were changed by this reviewer. Postmerge acceptance remains pending actual main integration.

## Platform and commands

Actual execution: Windows 10 build 19045, PowerShell driver, native cmd.exe and bundled Python 3.12.14 (MSC v.1944 AMD64) at `C:/Users/sibiya666/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe`. Repository: `C:/Users/sibiya666/Documents/projects/vizualization/task-tower`.

Command: `<python> -m unittest discover -s tests -v`.
Result: 56 tests in 15.989s, OK, 1 skipped (`test_refuses_symlink_state_directory`: symlinks unavailable). This includes bootstrap real subprocess tests, task stage/evidence/postmerge guards and existing readiness/process tests.

Independent acceptance driver: Python tempfile project whose name contains Cyrillic and spaces; custom descriptor invokes the same native Python executable with a fixture script, writes received cwd/context/argv, exits 23. No model, credentials, installation or overlay launch.

- `bootstrap.py --project <project> --harness custom --adapter <adapter> --superpowers <skill> --dry-run`: exit 0, no `.task-tower` or fixture output.
- Same setup with `--configure-only`: exit 0, persisted config, no fixture output.
- Change source adapter to `{}`, then `bootstrap.py --project <project> --launch`: exit 23, proving saved descriptor snapshot reuse and subprocess exit propagation.
- Fixture assertions passed: exact selected project cwd, context contains pinned skill path and Superpowers, `{project}` and literal `literal & spaces` preserve argument boundaries.
- Modify skill then repeat `--launch`: exit 2, no fixture output; stale pin refused.
- `cmd.exe /d /c start.cmd --help` with inherited PATH: exit 2 and explanatory missing-Python message. This environment exposes Python by explicit bundled path rather than PATH.
- Repeat wrapper with bundled Python directory prepended to child PATH: `--help` exits 0 and prints bootstrap arguments.
- Same PATH, `cmd.exe /d /c start.cmd --definitely-invalid-option`: PASS on retest, exits 2 and prints argparse error. Initial review exposed an erroneous exit 0; executor corrected wrapper control flow, added a regression test, and this reviewer independently reran the complete fixture driver successfully.

Driver was stored in OS temporary directory. Final retest exited 0 after every independent fixture assertion and both native wrapper assertions passed. The full suite additionally passed native Windows junction rejection regressions for harness state and task cards, including fallback behavior without the newer pathlib detector.

## Scope and pending evidence

macOS/Linux CI jobs were not run by this reviewer; workflow presence is not passing-platform evidence. Native harness/model sessions, actual paid calls and overlay were deliberately not launched. Symlink refusal remains unverified on this Windows account due to unavailable symlink creation. No postmerge or night-readiness claim is made.

## SHA-256 at final passing review

Hashes cover bootstrap entrypoints, CLI sources and all CLI test files as independently tested. Changes after this snapshot require renewed verification.

- `bootstrap.py`: `5df8d016d1e46343792c01bdc598e1d24881e9108486b0bbce81035ed08b5da2`
- `start.cmd`: `c6616cb26097c265ae968466eb93ceabdbf5c14082ef7f703334d15d14b02ef0`
- `start.sh`: `587f1d028c8b5f8c19333c7b6ddfe3ce71f5ab5d0905c90d9872044231999b37`
- `task_tower/__init__.py`: `c671ebd60f83582eb92badcb0aa8cbd5a259904eaee08ee9620012ee6a9f9ef0`
- `task_tower/__main__.py`: `e51a22a726ecc5fa5e0681ee938b565523452bad5ccde02c5c02a00aae0306f7`
- `task_tower/bootstrap.py`: `917963347081134ffd578220e4734d78cecb156771c1da9fc803174556bd322f`
- `task_tower/harness.py`: `89e2792875cd2bf2d5a18e638b6894e775e1ef67b1e79ec1c6643bd762125ddb`
- `task_tower/processes.py`: `326edff256d2c41b05a084d16ec6ee81ef50bcb8a58158b8a10df664f021be6b`
- `task_tower/readiness.py`: `99b7ba8fb024a6b22bf31242c324f1fe7a77bfc31090d7facc32580538d98070`
- `task_tower/tasks.py`: `e4f7c4160670710b07c26e4ec76f6800fbdb0343376f997dc4eaa85df1672f46`
- `task_tower/windows_job.py`: `d26cd1eb1f0d5b7b316114a4bfd6790757cf52f023e9cc40351e8563bbe7dce8`
- `tests/test_bootstrap.py`: `fe2e098c45c936be049c7524ac36d9506504f087cc55fb3488570430244ace73`
- `tests/test_cli.py`: `9834c9141d8f162b0ff0217a5a7360d149f8d05cbbd8edd8e02468f760d1ee79`
- `tests/test_harness.py`: `996a7a43900434c6b6a8e31c07a04224dd56a66cb2d2119aed766c3a9dd56ae5`
- `tests/test_processes.py`: `d4f239d92a3c13d765b0493bc2df33699ac24679150adbc32bf55cc3a1f5baa5`
- `tests/test_readiness.py`: `ecffb870e6a6cb39264831515383a4b5fcc75f6ab829eca005a6cd5db3d31629`
- `tests/test_task_cli.py`: `cbd6268521debad9b5bbae6b7120535b043f0ae6e6d991eb6b756915e763aaad`
- `tests/test_tasks.py`: `2c4f89c6017034ed300b0d0b73215077cafffb08fe3f28f2c60e1a27f266797a`
