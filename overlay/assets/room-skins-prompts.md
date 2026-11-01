# Complete room scenes — 2026-11-01

Generated with the built-in imagegen tool. Every file is an independent whole interior, never a repeated tower section. Sources are preserved in `assets/room-skins/`; runtime PNGs, glass masks and light anchors are prepared by `prepare-room-skins.cjs`.

Shared prompt: one coherent shallow cutaway gothic fantasy room, front-facing, wide landscape composition, one continuous back wall and level stone floor, enclosing side walls at the outer edges only. No facade, turrets, repeated modules, partitions, people, or text. Detailed crisp pixel clusters, blue-grey dimensional stone, muted silver edges, dark blue night windows and amber candles. Transparent outside the room silhouette. Furniture restricted to the rear 55%; front 40% clear slate floor for employees.

| Tier | Variant 0 | Variant 1 | Variant 2 |
| --- | --- | --- | --- |
| cabinet (1–4) | Astrologer's study, telescope, star charts, astrolabe | Chronicler's cell, books and manuscripts | Alchemy cell, glass vials, herbs, stone bench |
| workshop (5–8) | Rune workshop, engraved stones and tools | Cartography room, map table and globe | Tower library, book gallery and ladder |
| hall (9–16) | Council chamber, vault, banners and rear council table | Scriptorium, stained glass and chandeliers | Artifact forge, furnace, anvils and assembly benches |
| wings (17+) | Guild headquarters, command map and side work areas | Underground archive, vaults, niches and shelves | Order observatory, starry glass dome and giant astrolabe |

Session ID deterministically selects the variant (0–2). Capacity tier is captured when entering the session scene and retained until leaving. Every agent remains visible, with depth-sorted sprites and individual tooltip hitboxes. Ambient clouds are masked to blue glass; warm animated light is clipped to the scene silhouette.
