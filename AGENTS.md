# Task Tower

Superpowers is the mandatory development process. Read the architecture spec and applicable implementation plan under docs/superpowers before changing behavior. Apply applicable brainstorming, planning, TDD, independent review and verification skills; record evidence rather than claiming a stage passed.

Preserve unrelated project changes. Use isolated working copies for project execution; a worktree is not a process or credential sandbox. Never write Codex internal databases or expose credentials. No installation or model selection is required by the readiness milestone.

Run the complete test suite: `python -m unittest discover -s tests -v` (Python 3.11+). No third-party dependencies. Executors and reviewers are distinct instances. Do not claim pilot or night readiness without the evidence required by the spec.

## Project-first setup

Follow [clean-clone GitHub setup](docs/github-setup.md) and [bootstrap/custom harness instructions](docs/bootstrap.md). For creation workflows, establish an authenticated, writable repository-linked Project and complete Status mapping through `python -m task_tower connect` (or explicit bootstrap GitHub flags) before importing Issues. A bare URL/read-only connection or local-only harness setup is not full readiness. Preserve existing Issues, prose, options and private connections; recover partial creation by retrying the same identity, never deleting resources or blindly recreating them. Serialize initial setup across hosts; discovery is not a distributed creation lock.

Authentication and project scope authorization are explicit human steps; never run hidden scope grants, install tools, select models or store secrets in connections. Private installation config lives outside source checkouts. GitHub connector/Git transport login does not establish local CLI Projects access. Current sequencing and capability limits are in [roadmap](docs/roadmap.md): #24 precedes #14; development executors, autonomous callbacks/resume and daemon orchestration remain planned. The existing PR acceptor and chat orchestration are distinct from a background PR worker.

## Unified repository

Backlog semantics: large features use native parent Issues and sub-issues; milestones are implementation stages/releases, not feature parents. Preserve these separate relationships and repository-qualified identities. The three books contain proposals (Ideas), stage/feature/task projections (Tasks), and linked repository artifacts (Project library). Hierarchical bookshelf rendering remains planned in #22/#23; do not claim the current flat CLI/HTML snapshot implements it. See docs/github-books.md.

The readiness CLI (`task_tower/`) and Windows overlay (`overlay/`) are one product with separate modules. The overlay monitors actual sessions; the CLI audits readiness. Private project connections aggregate GitHub Issues and repository Markdown into CLI/HTML books. The project worker supports Actions-serialized postmerge acceptance only; development execution, automated merging and overlay book integration remain planned. Canonical overlay code is in `overlay/`; external old launch paths are compatibility entry points. Preserve unrelated changes and do not commit/push unless requested.

## Overlay invariants

- Project = tower, session = floor, agents = employees. Exclude guardian internals, resolve nested children and never infer activity from decorative animation.
- Draw one whole interior, never concatenate tower facades. Four capacity tiers, three variants each. Capture tier on entry and preserve until leaving; variant is deterministic by session ID.
- Show all current agents. Newly seen agents enter once, completed/removed agents exit once and disappear; historical completed agents are not occupants. Keep stable models, depth sorting and individual tooltip hitboxes aligned with sprites. Hourglasses mean explicit unresolved user decisions, never generic idle or completed work. Do not infer questions from arbitrary message prose.
- Minimal transparent UI: overview pin/close, room back/pin/close. No restored footer, captions or combined room tooltip. Drag threshold is 5 px and dragging must not open a floor.
- Room placement is clamped to the current monitor work area with DPI/negative coordinates considered. Save overview bounds separately and restore them on return, together with canvas scroll; room dragging must not overwrite overview placement.
- Preserve aspect ratios, true alpha, reduced motion, composition WebView2, CSP and restricted native message origin/actions.
- Read Codex SQLite in mode=ro; never mutate Codex internals. Stale/unknown states must not claim confirmed work. Runtime snapshots, logs, browser profiles and project assignments stay out of Git. Diagnose using the snapshot referenced by overlay-source.json.

## Art and documentation

Keep originals/prompts under `overlay/assets/`. Apply imagegen for raster creation and PixelFX for suitable procedural effects; retain licenses and NOTICE. Preparation tools generate `web/assets/`, `room-skins.js` and `tower-art.css`; edit sources/tools rather than generated metadata.

Documentation images belong in `docs/screenshots/`. Preserve raw user screenshots separately, label background cleanup and never present generated mockups as raw captures. Presentation exports use a common canvas, proportional scaling and transparent PNG. Exclude unrelated desktop content and private logs.

## Verification

From overlay/: `python -m unittest -v`, `node --test test-web.cjs test-room-skins.cjs test-presence.cjs test-presence-browser.cjs test-scene-position.cjs`; run native `powershell.exe -NoProfile -ExecutionPolicy Bypass -STA -File overlay.ps1 -SmokeTest` after host/launch/render changes. Browser tests require Playwright, Sharp and Edge (current bundled paths are machine-specific). CLI tests remain dependency-free and must pass after integration.

PowerShell 5.1 scripts with Cyrillic must be UTF-8 BOM. The desktop shortcut must target `overlay/launch-codex-tower.ps1` and its assets icon. Keep old launch entry points working when moving files.
