# Visual world — local review candidate

Issues: #31–35. User requested implementation and approved local-time lighting, manual weather and a 30-minute idle timeout. Implementation was developed in an isolated Git worktree and copied into the canonical overlay after validation without touching unrelated task-manager files. No commit, push, issue closure or merge is claimed.

Implemented:

- Compact distant silhouette for >8 sessions, true floor-count badge, all actual sessions selectable and optional full-floor rendering. Shapes retain uniform scaling. Rounded grouping is shared by lighting and hitboxes.
- Local-time dawn/day/dusk/night with manual day/night overrides, smooth tint and unchanged real activity lights.
- Two non-interactive transparent cloud layers behind towers; selectable clear/clouds/rain/fog, effect-disable and reduced-motion support.
- Local idle tracking persisted across restarts, 10/30/60-minute/off choices, explicit show-hidden override, revival on activity and protection for waiting/unknown/stale/error states. New completion timestamps advance old idle baselines.
- Settings via scene right-click, keyboard Escape dismissal; no permanent settings panel or new network request.

Verification:

- Collector: 18 tests passed.
- Node/browser: 14 tests passed (including five world-policy cases and world integration coverage).
- Existing CLI: 69 tests ran successfully, 1 skipped.
- Native smoke passed in worktree and canonical application: transparent composition, clear alpha, controls, live towers and window navigation.
- Day/cloud and night/rain previews inspected; opaque rain haze/floor and baked cloud moon removed from licensed local PixelFX recipes. Runtime atlas frames and reduced-motion render on transparency.
- Independent review identified idle-baseline and uneven floor-group hitbox defects; both fixed with regressions.

Visual review remains pending with the owner, especially the compact distant representation and atmosphere strength. Keep issues open until review and normal acceptance/merge.
