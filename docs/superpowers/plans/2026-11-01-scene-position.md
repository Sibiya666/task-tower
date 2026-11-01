# Scene positioning

Implement the positioning part of the recorded idea: restore overview bounds and canvas scroll after visiting a room; keep opened rooms inside the selected monitor's work area. Compact tower spacing remains a separate idea.

1. Add a browser regression for horizontal/vertical overview scroll surviving room navigation, room viewport resize and snapshot updates.
2. Save native overview bounds before switching; clamp rooms against the nearest monitor work area (including negative monitor coordinates and DPI conversion); restore saved overview bounds independently of room dragging.
3. Save/restore scroll before hiding/after showing overview. Extend native smoke with edge clamping and moved-room return checks. Run browser, collector and native checks; independently review. Preserve unrelated work; no automatic commit or push.
