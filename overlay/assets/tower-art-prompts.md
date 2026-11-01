# Tower modules

## Interior and employees

`gothic-interior-source.png` was generated using the coherent exterior as an imagegen style reference: one front-facing gothic interior cutout, volumetric blue-gray masonry and bone bevels, two pointed lattice windows, central column, carved corbels, rear workbench and candles, clear lower floor for separate characters, transparent outer silhouette, no people or UI. Runtime: `web/assets/gothic-interior.png`, contained without aspect distortion in a 386×448 canvas.

`employee-sprites-source.png` was generated with the exterior and interior as style references: four separate front-facing full-body adventurer workers on a transparent sheet, equal-width quarters and shared baseline — burgundy scholar with book, armored blacksmith with hammer, green ranger inspector with parchment, blue coordinator mage with staff. No labels, environment, status icons or ground. `prepare-employees.cjs` extracts the quarters and prepares `employee-{scholar,smith,ranger,mage}.png` at 84×88.

Runtime employee motion is Canvas animation: subtle idle breathing, active body lift/lean and breathing, still stopped/unknown/error characters. Status icons are drawn independently and remain steady. System reduced-motion preference disables character motion.

## Current coherent tower

## Fantasy ground

Generated with built-in imagegen, referencing `tower-icon.png`: isolated low irregular oval ground patch, ancient cobblestones and flat foundation slabs, dark mossy grass, loose angular rocks, sparse blue-green weeds, short stone path toward viewer; shallow three-quarter game view, dimensional crisp pixel art in the tower's palette, transparent alpha outside natural perimeter, no buildings, scenery, labels or rectangular tile. Original: `fantasy-ground-source.png`; runtime trimmed/resized PNG: `../web/assets/fantasy-ground.png`.

## Coherent building source

The runtime now uses `tower-unified-source.png`, generated in one imagegen call with the desktop icon as the style reference. Prompt: one complete gothic tower in strict straight-on orthographic elevation; one central vertical axis, symmetrical facade, no visible side face, no tilted or diagonal cornices; slate spire and turrets, exactly one dark-window story between two horizontal cornices, and a centered stone entry base. All windows unlit; charcoal, blue-gray stone and bone highlights, transparent background, crisp dimensional pixel art.

`prepare-unified-tower.cjs` slices that ONE canvas at Y=548 and Y=953, retaining shared X=128 and width=768 for every part. It generates aligned roof/floor/base PNGs, a glass-only light mask, and `web/tower-art.css` with measured part heights. No independent horizontal crop or recentering is performed. Slice metadata is in `tower-alignment.json`. The earlier separate modules below are preserved as source history and are no longer used for runtime drawing.

Generated with the built-in imagegen tool using `tower-icon.png` as the style reference. Transparent PNG source files are preserved here; `prepare-tower-art.cjs` trims clear margins and produces 512 px wide runtime sprites without changing their aspect ratios.

- Floor: a repeatable middle section in three-quarter orthographic view, cool volumetric gothic masonry, chamfered stone cornices, two front pointed-arch dark windows and one narrow right-side window. No roof, door, text or emitted light. Source `tower-floor-source.png`.
- Roof: isolated blue slate conical spire, iron finial, corner turrets and carved crenellated cornice; no middle floors or door. Same reference, materials and view. Source `tower-roof-source.png`.
- Base: isolated foundation module with gothic iron-banded wooden door, thick corner buttresses and attached stone steps; no roof or upper floors. Same reference and view. Source `tower-base-source.png`.

Palette: charcoal #0c1114, blue-gray #344348, cool stone #71858c, bone #d8d5c6. Active light is applied by the app from actual session status, never baked into the repeatable floor.
