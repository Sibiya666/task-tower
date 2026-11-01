# Overlay integration verification — 2026-11-01

Canonical code moved into `overlay/` beside the existing readiness CLI. Workspace-root launchers forward to the new location; previous sources are retained under local runtime backup. Desktop shortcut was updated and its target/icon verified. Codex data was not modified.

Checks from the new location:

- CLI: `python -m unittest discover -s tests -v` — 26 passed.
- Overlay collector: `python -m unittest -q` — 12 passed.
- Browser: `node --test test-web.cjs test-room-skins.cjs` — 2 passed.
- Native `overlay.ps1 -SmokeTest` — PASS: transparent composition window, alpha background, native pin controls, live towers and wide-window layout.
- Old root `launch-codex-tower.ps1 -CheckOnly` resolves the new overlay script and icon.
- Documentation exports: three PNGs, each 960×640, alpha present with fully transparent pixels, proportional fit.
- Git ignore check confirms local `overlay/runtime/` and `overlay/project-map.json` are excluded.

Documentation uses user-supplied screenshots; originals and processed versions are separately labelled. No queue/model execution/automerge readiness is claimed. Changes have not been committed or pushed by this integration task.
