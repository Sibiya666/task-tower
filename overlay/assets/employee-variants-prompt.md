# Employee variants — 2026-11-01

Generated with the built-in imagegen tool, using `employee-sprites-source.png` as the style reference. Source: `employee-variants-source.png`. Transparent 3×3 atlas, sliced by `prepare-employee-variants.cjs` into nine 84×88 sprites with a shared baseline.

Prompt: nine distinct full-body dark gothic fantasy pixel-art employees, strict equal 3-column × 3-row grid, transparent gutters and background, no labels or scenery, matching the reference's crisp clusters, top-left lighting and muted stone-blue/burgundy/olive/leather palette. Top row: silver-haired armored female artificer with wrench, black-bearded dwarf machinist with goggles and hammer, auburn-haired engineer with calipers. Middle row: grey-haired cloaked scout with checklist, hooded veteran inspector with lantern, female leather-armored ranger with crossbow. Bottom row: elderly burgundy scholar with book, plum-robed female alchemist with flask and notebook, navy/maroon scribe with spectacles and compass. Distinct silhouettes and equipment rather than recolors; readable at 42×44.

Runtime: each scholar/smith/ranger family retains its original sprite plus three new models. Model selection is deterministic by agent ID; the main agent retains the mage model. Existing breathing/work animation applies to every model.
