# Visual audit of PR 36

The owner reported at least two visual defects and an offscreen settings panel. Merge was held while investigating. The following issues were independently reproduced on fixture scenes; fixture screenshots are not claimed as user-session captures.

| Defect | Reproduction | Fix / regression |
| --- | --- | --- |
| Left tower clipped | Three projects at 650 px, fixed 740 px field | Responsive 1–3 columns and stable slots; test widths 470/650/1000, no horizontal overflow |
| Expanded roof escapes plot | Show all 16 floors in distant tower | Reserve depth lift before computing uniform scale; assert art remains inside plot |
| Floating horizontal splash strip | Rain atlas stretched to full window | Render rain streak region without the atlas ground band |
| Native window/menu offscreen | Drag overview beyond work area, open settings | Clamp after drag/resize and before settings; recover out-of-bounds overview, resize to smaller work area if needed; native smoke regression |
| Popup remains outside after viewport shrink | Open settings, resize to 340×300 | Reposition open popup on resize; assert full popup bounds |
| Day/night unclear | Compare brightness-only modes | Add pixel sun/moon and readable current-phase/mode text in settings |

Tests include the existing project-slot stability, return scroll, individual employee/status and source freshness regressions. Reduced motion keeps celestial indicators and freezes weather motion. Transparent backgrounds remain; weather does not capture pointer input.

The updated policy intentionally stops preserving a partially offscreen overview: the owner's new requirement is that all controls/settings remain within the monitor work area. Valid saved positions still restore exactly.
