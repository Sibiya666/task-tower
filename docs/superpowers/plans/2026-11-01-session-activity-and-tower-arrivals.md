# Session activity, floor identity and tower arrivals

User requested fixing an unlit renamed session and an extra third floor, then right-aligning towers near controls and animating a new working agent entering the tower door on overview. Keep unrelated task-manager changes excluded from this PR.

Evidence: live data showed an old async decision survived actual replies recorded as response_item/message with role=user, rather than event_msg/user_message. The third floor was a source=exec, has_user_event=0 non-interactive review without a parent; it was not a third user chat.

- Recognize real user message metadata in incremental reads and large-tail backscan; keep active status when the turn already started. Do not retain message bodies.
- Exclude root non-interactive exec runs from chat floors, preserving explicit parented executions as employees. Read has_user_event with a compatibility fallback for older schemas.
- Anchor plots from the right; compensate horizontal scrolling as the reserved field grows to preserve existing tower positions.
- Detect new visible working agent IDs across fresh snapshots. On overview only, draw a small character approaching the door and fading inside. No initial-load replay, repeated-snapshot replay, stale-source or reduced-motion animation.
- Regression tests cover both collector issues, rename/light pixels, right alignment, stable plots, arrival expiry and reduced motion. Run native smoke and independent review before publishing PR.
