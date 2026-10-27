---
name: dock-magnify-headroom
description: "ii dock magnify-on-hover clipping fix — QML anchor gotcha in Dock.qml, patched live 2026-09-08"
metadata: 
  node_type: memory
  type: project
  originSessionId: cc1e8b2e-233b-4ce0-8cc0-2a624d73e526
  modified: 2026-09-07T19:10:06.872Z
---

ii's dock (`~/.config/quickshell/ii/modules/ii/dock/`) magnifies icons on hover via `scale`
with `transformOrigin: Item.Bottom`, so icons grow upward and were being cut off at the
layer-shell surface's top edge. Fixed 2026-09-08 in `Dock.qml` by adding a `magnifyHeadroom`
property — `(dock.height + hyprlandGapsOut * 2) * (magnifyMaxScale - 1)` — to the
PanelWindow's `implicitHeight`, subtracting it from `dockBackground.height`, and excluding it
from `exclusiveZone` so pinning doesn't over-reserve screen space. Also: `DockButton`'s
`background.implicitHeight` now tracks `dock.height + elevationMargin` instead of a hardcoded
50 (the 50 only fit dock.height 60, so slimming the dock pushed icons and their indicator dots
out the pill's bottom); `DockAppButton` uses `padding: 4` and derives `iconSize` from its own
content box; and `IconImage.implicitSize` is `iconSize * magnifyMaxScale` so hover magnification
doesn't upscale a too-small texture and go blurry. `dock.height` 48 read as too small — back at 60.

**Why:** The first attempt failed because `dockBackground` had `anchors.top` *and*
`anchors.bottom` *and* an explicit `height:` — with both opposing anchors set, the anchors win
and the `height:` line is dead code, so the pill stretched over the headroom instead of
leaving it free. That line was always dead; adding headroom just made it visible.

**How to apply:** In QML, never set an explicit `height` alongside both `anchors.top` and
`anchors.bottom` — drop one anchor. Verify dock geometry without guessing by reading the real
surface size: `hyprctl layers -j` and look for namespace `quickshell:dock`. Related:
[[ii-dots-install]].
